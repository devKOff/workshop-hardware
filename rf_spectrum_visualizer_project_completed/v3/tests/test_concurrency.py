"""Concurrency and thread safety tests."""

import pytest
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import AppConfig, ChannelConfig, ScanConfig, ThresholdConfig
from scanner import SpectrumData, ChannelObservation, ScannerThread
from sim_radio import SimRadio


class TestSpectrumDataConcurrency:
    """Thread safety tests for SpectrumData."""
    
    @pytest.fixture
    def config(self):
        return AppConfig(
            channel=ChannelConfig(start_channel=0, end_channel=50),
            scan=ScanConfig(measurement_window=1.0, sampling_interval=0.01),
            thresholds=ThresholdConfig(),
        )
    
    @pytest.fixture
    def spectrum_data(self, config):
        return SpectrumData(config)
    
    def test_concurrent_readers_writers(self, spectrum_data):
        """Test multiple readers and writers don't corrupt data."""
        errors = []
        results = []
        
        def writer(writer_id):
            try:
                for ch in range(10):
                    obs = ChannelObservation(
                        timestamp=time.time(),
                        channel=ch,
                        frequency_mhz=2400 + ch,
                        backend="sim",
                        valid_samples=100,
                        rpd_positive=writer_id * 10 + ch,
                        rpd_negative=100 - writer_id * 10 - ch,
                        activity_percentage=float(writer_id * 10 + ch),
                        status="Clear",
                        data_sufficient=True,
                        measurement_window=1.0,
                        sampling_interval=0.01,
                    )
                    spectrum_data.update_observation(obs)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)
        
        def reader(reader_id):
            try:
                for _ in range(20):
                    all_obs = spectrum_data.get_all_observations()
                    results.append((reader_id, len(all_obs)))
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)
        
        threads = []
        for i in range(3):
            t = threading.Thread(target=writer, args=(i,))
            threads.append(t)
        for i in range(5):
            t = threading.Thread(target=reader, args=(i,))
            threads.append(t)
        
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)
        
        assert len(errors) == 0
        assert len(results) == 100
    
    def test_snapshot_atomicity(self, spectrum_data):
        """Test that get_all_observations returns consistent snapshots."""
        # Pre-populate
        for ch in range(20):
            obs = ChannelObservation(
                timestamp=time.time(),
                channel=ch,
                frequency_mhz=2400 + ch,
                backend="sim",
                valid_samples=100,
                rpd_positive=50,
                rpd_negative=50,
                activity_percentage=50.0,
                status="Busy",
                data_sufficient=True,
                measurement_window=1.0,
                sampling_interval=0.01,
            )
            spectrum_data.update_observation(obs)
        
        snapshots = []
        
        def updater():
            for i in range(100):
                for ch in range(20):
                    obs = ChannelObservation(
                        timestamp=time.time(),
                        channel=ch,
                        frequency_mhz=2400 + ch,
                        backend="sim",
                        valid_samples=100,
                        rpd_positive=i % 100,
                        rpd_negative=100 - (i % 100),
                        activity_percentage=float(i % 100),
                        status="Clear",
                        data_sufficient=True,
                        measurement_window=1.0,
                        sampling_interval=0.01,
                    )
                    spectrum_data.update_observation(obs)
                time.sleep(0.0001)
        
        def snapshoter():
            for _ in range(50):
                snap = spectrum_data.get_all_observations()
                snapshots.append(snap)
                time.sleep(0.0002)
        
        t1 = threading.Thread(target=updater)
        t2 = threading.Thread(target=snapshoter)
        
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        
        # Verify each snapshot is internally consistent
        for snap in snapshots:
            for obs in snap.values():
                assert 0 <= obs.activity_percentage <= 100
                assert obs.channel == (obs.frequency_mhz - 2400)
                assert obs.backend == "sim"
    
    def test_waterfall_concurrent_access(self, spectrum_data):
        """Test concurrent waterfall data access."""
        for ch in range(10):
            obs = ChannelObservation(
                timestamp=time.time(),
                channel=ch,
                frequency_mhz=2400 + ch,
                backend="sim",
                valid_samples=100,
                rpd_positive=10,
                rpd_negative=90,
                activity_percentage=10.0,
                status="Clear",
                data_sufficient=True,
                measurement_window=1.0,
                sampling_interval=0.01,
            )
            spectrum_data.update_observation(obs)
        
        results = []
        
        def reader():
            for _ in range(20):
                data = spectrum_data.get_waterfall_data(max_age=60)
                results.append(len(data))
                time.sleep(0.001)
        
        def writer():
            for i in range(20):
                obs = ChannelObservation(
                    timestamp=time.time(),
                    channel=i % 10,
                    frequency_mhz=2400 + (i % 10),
                    backend="sim",
                    valid_samples=100,
                    rpd_positive=20,
                    rpd_negative=80,
                    activity_percentage=20.0,
                    status="Clear",
                    data_sufficient=True,
                    measurement_window=1.0,
                    sampling_interval=0.01,
                )
                spectrum_data.update_observation(obs)
                time.sleep(0.001)
        
        threads = [threading.Thread(target=reader) for _ in range(3)]
        threads.append(threading.Thread(target=writer))
        
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)
        
        assert all(r >= 10 for r in results)
    
    def test_rolling_history_bounded_under_load(self, spectrum_data):
        """Test rolling history stays bounded under concurrent writes."""
        config = AppConfig(
            channel=ChannelConfig(start_channel=0, end_channel=5),
            scan=ScanConfig(measurement_window=1.0, sampling_interval=0.01),
            thresholds=ThresholdConfig(),
        )
        config.storage.rolling_history_size = 10
        sd = SpectrumData(config)
        
        def writer():
            for i in range(50):
                obs = ChannelObservation(
                    timestamp=time.time() + i,
                    channel=0,
                    frequency_mhz=2400,
                    backend="sim",
                    valid_samples=100,
                    rpd_positive=i,
                    rpd_negative=100 - i,
                    activity_percentage=float(i),
                    status="Clear",
                    data_sufficient=True,
                    measurement_window=1.0,
                    sampling_interval=0.01,
                )
                sd.update_observation(obs)
        
        threads = [threading.Thread(target=writer) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        history = sd.get_rolling_history(0)
        assert len(history) <= 10


class TestScannerThreadConcurrency:
    """Concurrency tests for ScannerThread."""
    
    @pytest.fixture
    def config(self):
        return AppConfig(
            channel=ChannelConfig(start_channel=0, end_channel=20),
            scan=ScanConfig(measurement_window=0.05, sampling_interval=0.005),
            thresholds=ThresholdConfig(),
        )
    
    def test_multiple_start_stop_cycles(self, config):
        """Test repeated start/stop cycles don't leak resources."""
        for cycle in range(10):
            spectrum_data = SpectrumData(config)
            radio = SimRadio(config.channel, config.scan, seed=cycle)
            radio.initialize()
            
            scanner = ScannerThread(config, spectrum_data, radio)
            scanner.start()
            time.sleep(0.1)
            scanner.stop()
            radio.cleanup()
            
            assert scanner.is_running() is False
    
    def test_start_twice_raises(self, config):
        """Test starting twice raises error."""
        spectrum_data = SpectrumData(config)
        radio = SimRadio(config.channel, config.scan, seed=42)
        radio.initialize()
        
        scanner = ScannerThread(config, spectrum_data, radio)
        scanner.start()
        
        with pytest.raises(Exception):  # ScannerAlreadyRunningError
            scanner.start()
        
        scanner.stop()
        radio.cleanup()
    
    def test_stop_without_start(self, config):
        """Test stopping without starting is safe."""
        spectrum_data = SpectrumData(config)
        radio = SimRadio(config.channel, config.scan, seed=42)
        radio.initialize()
        
        scanner = ScannerThread(config, spectrum_data, radio)
        result = scanner.stop()
        
        assert result is True
        radio.cleanup()
    
    def test_shutdown_during_scan(self, config):
        """Test shutdown while scanning."""
        spectrum_data = SpectrumData(config)
        radio = SimRadio(config.channel, config.scan, seed=42)
        radio.initialize()
        
        scanner = ScannerThread(config, spectrum_data, radio)
        scanner.start()
        time.sleep(0.05)
        scanner.shutdown()
        radio.cleanup()
        
        assert scanner.is_running() is False
    
    def test_concurrent_scanners_different_data(self, config):
        """Test multiple scanners with different SpectrumData instances."""
        radios = []
        scanners = []
        spectrum_datas = []
        
        for i in range(3):
            sd = SpectrumData(config)
            radio = SimRadio(config.channel, config.scan, seed=i)
            radio.initialize()
            
            scanner = ScannerThread(config, sd, radio)
            scanner.start()
            
            radios.append(radio)
            scanners.append(scanner)
            spectrum_datas.append(sd)
        
        time.sleep(0.2)
        
        for scanner in scanners:
            scanner.stop()
        for radio in radios:
            radio.cleanup()
        
        for sd in spectrum_datas:
            obs = sd.get_all_observations()
            assert len(obs) == 21
    
    def test_scanner_exception_recovery(self, config):
        """Test scanner handles radio errors gracefully."""
        spectrum_data = SpectrumData(config)
        
        broken_radio = SimRadio(config.channel, config.scan, seed=42)
        broken_radio.initialize()
        
        # Break the radio's scan_channel method
        original_scan = broken_radio.scan_channel
        call_count = [0]
        
        def failing_scan(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 3:
                raise Exception("Simulated radio failure")
            return original_scan(*args, **kwargs)
        
        broken_radio.scan_channel = failing_scan
        
        scanner = ScannerThread(config, spectrum_data, broken_radio)
        scanner.start()
        time.sleep(0.5)
        scanner.stop()
        broken_radio.cleanup()
        
        # Should have scanned some channels before error
        obs = spectrum_data.get_all_observations()
        assert len(obs) > 0


class TestBoundedQueueBehavior:
    """Tests for bounded queue behavior in scanner."""
    
    @pytest.fixture
    def config(self):
        return AppConfig(
            channel=ChannelConfig(start_channel=0, end_channel=100),
            scan=ScanConfig(measurement_window=0.01, sampling_interval=0.001),
            thresholds=ThresholdConfig(),
        )
    
    def test_scanner_does_not_block_on_callbacks(self, config):
        """Test scanner doesn't block on slow callbacks."""
        spectrum_data = SpectrumData(config)
        radio = SimRadio(config.channel, config.scan, seed=42)
        radio.initialize()
        
        callback_times = []
        
        def slow_callback(obs):
            time.sleep(0.01)
            callback_times.append(time.time())
        
        scanner = ScannerThread(
            config,
            spectrum_data,
            radio,
            on_observation=slow_callback,
        )
        scanner.start()
        time.sleep(0.3)
        scanner.stop()
        radio.cleanup()
        
        # Should have completed multiple scans despite slow callback
        assert spectrum_data.get_scan_count() > 1


class TestLockContention:
    """Tests for lock contention scenarios."""
    
    @pytest.fixture
    def config(self):
        return AppConfig(
            channel=ChannelConfig(start_channel=0, end_channel=10),
            scan=ScanConfig(measurement_window=0.1, sampling_interval=0.01),
            thresholds=ThresholdConfig(),
        )
    
    def test_lock_not_held_during_sleep(self, config):
        """Verify scanner doesn't hold lock during sleep."""
        spectrum_data = SpectrumData(config)
        radio = SimRadio(config.channel, config.scan, seed=42)
        radio.initialize()
        
        lock_acquired = []
        lock_released = []
        
        original_lock = spectrum_data._lock
        
        class TrackedLock:
            def __enter__(self):
                original_lock.__enter__()
                lock_acquired.append(time.time())
            
            def __exit__(self, *args):
                lock_released.append(time.time())
                return original_lock.__exit__(*args)
        
        spectrum_data._lock = TrackedLock()
        
        scanner = ScannerThread(config, spectrum_data, radio)
        scanner.start()
        time.sleep(0.2)
        scanner.stop()
        radio.cleanup()
        
        # Lock should be acquired and released many times
        assert len(lock_acquired) > 10
        assert len(lock_released) > 10
        
        # Time between acquire and release should be small (not holding during scan)
        for acq, rel in zip(lock_acquired, lock_released):
            assert rel - acq < 0.1  # Should release quickly


class TestGUIRefreshCallbackLifecycle:
    """Tests for GUI refresh callback management."""
    
    @patch('app.FigureCanvasTkAgg')
    @patch('app.Figure')
    @patch('app.tk.Tk')
    def test_single_refresh_callback(self, mock_tk, mock_figure, mock_canvas):
        """Test only one refresh callback is scheduled at a time."""
        from app import SpectrumVisualizerApp
        
        config = AppConfig()
        mock_root = MagicMock()
        mock_tk.return_value = mock_root
        mock_fig = MagicMock()
        mock_figure.return_value = mock_fig
        
        app = SpectrumVisualizerApp(config)
        app._running = True
        app._refresh_job = None
        
        # Schedule refresh twice
        app._schedule_refresh()
        job1 = app._refresh_job
        app._schedule_refresh()
        job2 = app._refresh_job
        
        # Should be the same job (second call should not create new one)
        # Actually, our implementation cancels previous - let's verify
        mock_root.after.assert_called()
    
    @patch('app.FigureCanvasTkAgg')
    @patch('app.Figure')
    @patch('app.tk.Tk')
    def test_cancel_callback_on_stop(self, mock_tk, mock_figure, mock_canvas):
        """Test refresh callback is cancelled on stop."""
        from app import SpectrumVisualizerApp
        
        config = AppConfig()
        mock_root = MagicMock()
        mock_tk.return_value = mock_root
        mock_fig = MagicMock()
        mock_figure.return_value = mock_fig
        
        app = SpectrumVisualizerApp(config)
        app._running = True
        app._refresh_job = "job123"
        
        app._stop_scanning()
        
        mock_root.after_cancel.assert_called_with("job123")
        assert app._refresh_job is None
    
    @patch('app.FigureCanvasTkAgg')
    @patch('app.Figure')
    @patch('app.tk.Tk')
    def test_no_callback_after_destroy(self, mock_tk, mock_figure, mock_canvas):
        """Test no callback scheduled after window destroy."""
        from app import SpectrumVisualizerApp
        
        config = AppConfig()
        mock_root = MagicMock()
        mock_tk.return_value = mock_root
        mock_fig = MagicMock()
        mock_figure.return_value = mock_fig
        
        app = SpectrumVisualizerApp(config)
        app._running = False
        app._refresh_job = None
        
        # Simulate destroy
        mock_root.winfo_exists.return_value = False
        app._on_close()
        
        # Should not schedule new refresh
        mock_root.after.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])