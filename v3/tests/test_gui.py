"""Unit tests for GUI application (mocked for headless testing)."""

import pytest
import sys
from unittest.mock import Mock, MagicMock, patch, PropertyMock

# Mock tkinter and matplotlib before importing app
sys.modules['tkinter'] = MagicMock()
sys.modules['tkinter.ttk'] = MagicMock()
sys.modules['tkinter.filedialog'] = MagicMock()
sys.modules['tkinter.messagebox'] = MagicMock()
sys.modules['matplotlib'] = MagicMock()
sys.modules['matplotlib.figure'] = MagicMock()
sys.modules['matplotlib.backends.backend_tkagg'] = MagicMock()
sys.modules['matplotlib.colors'] = MagicMock()

import numpy as np
np.random.seed(42)

from app import SpectrumVisualizerApp, ChannelTableModel
from config import AppConfig, ChannelConfig, ScanConfig, ThresholdConfig
from scanner import ChannelObservation, SpectrumData


class TestChannelTableModel:
    """Tests for ChannelTableModel."""
    
    @pytest.fixture
    def config(self):
        return AppConfig(
            channel=ChannelConfig(start_channel=0, end_channel=5),
            scan=ScanConfig(measurement_window=1.0, sampling_interval=0.01),
            thresholds=ThresholdConfig(),
        )
    
    @pytest.fixture
    def model(self, config):
        return ChannelTableModel(config)
    
    def test_update_and_get(self, model):
        obs = ChannelObservation(
            timestamp=1234567890.0,
            channel=3,
            frequency_mhz=2403,
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
        
        model.update({3: obs})
        
        row = model.get_row_data(3)
        assert row is not None
        assert row["channel"] == 3
        assert row["activity_pct"] == 50.0
        assert row["status"] == "Busy"
    
    def test_get_nonexistent(self, model):
        row = model.get_row_data(99)
        assert row is None
    
    def test_get_all_channels(self, model):
        for ch in range(3):
            obs = ChannelObservation(
                timestamp=1234567890.0,
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
            model.update({ch: obs})
        
        channels = model.get_all_channels()
        assert channels == [0, 1, 2]


class TestSpectrumVisualizerApp:
    """Tests for SpectrumVisualizerApp (mocked GUI)."""
    
    @pytest.fixture
    def config(self):
        return AppConfig(
            channel=ChannelConfig(start_channel=0, end_channel=5),
            scan=ScanConfig(measurement_window=0.1, sampling_interval=0.01),
            thresholds=ThresholdConfig(),
            mitigation=MitigationConfig(armed=False),
        )
    
    @patch('app.FigureCanvasTkAgg')
    @patch('app.Figure')
    @patch('app.tk.Tk')
    def test_initialization(self, mock_tk, mock_figure, mock_canvas, config):
        mock_root = MagicMock()
        mock_tk.return_value = mock_root
        mock_root.winfo_exists.return_value = True
        
        mock_fig = MagicMock()
        mock_figure.return_value = mock_fig
        mock_ax = MagicMock()
        mock_fig.add_subplot.return_value = mock_ax
        
        mock_canvas_instance = MagicMock()
        mock_canvas.return_value = mock_canvas_instance
        
        app = SpectrumVisualizerApp(config)
        
        assert app._config == config
        assert app._running is False
        assert app._scanner is None
        mock_tk.assert_called_once()
        mock_root.title.assert_called_with("RF Spectrum Visualizer - 2.4 GHz ISM Band")
    
    @patch('app.FigureCanvasTkAgg')
    @patch('app.Figure')
    @patch('app.tk.Tk')
    def test_on_backend_change_stopped(self, mock_tk, mock_figure, mock_canvas, config):
        mock_root = MagicMock()
        mock_tk.return_value = mock_root
        
        mock_fig = MagicMock()
        mock_figure.return_value = mock_fig
        
        app = SpectrumVisualizerApp(config)
        app._backend_var = MagicMock()
        app._backend_var.get.return_value = "hardware"
        
        # Should work when not running
        app._running = False
        app._on_backend_change()
        
        assert app._config.default_backend == "hardware"
    
    @patch('app.FigureCanvasTkAgg')
    @patch('app.Figure')
    @patch('app.tk.Tk')
    @patch('app.messagebox')
    def test_on_backend_change_running(self, mock_msgbox, mock_tk, mock_figure, mock_canvas, config):
        mock_root = MagicMock()
        mock_tk.return_value = mock_root
        
        mock_fig = MagicMock()
        mock_figure.return_value = mock_fig
        
        app = SpectrumVisualizerApp(config)
        app._backend_var = MagicMock()
        app._backend_var.get.return_value = "hardware"
        
        # Should show warning when running
        app._running = True
        app._config.default_backend = "sim"
        app._on_backend_change()
        
        mock_msgbox.showwarning.assert_called_once()
        assert app._config.default_backend == "sim"
    
    @patch('app.FigureCanvasTkAgg')
    @patch('app.Figure')
    @patch('app.tk.Tk')
    @patch('app.HardwareRadio')
    @patch('app.SimRadio')
    @patch('app.ScannerThread')
    @patch('app.MitigationEngine')
    def test_start_scanning_sim(self, mock_mitigation, mock_scanner, mock_sim, mock_hw, mock_tk, mock_figure, mock_canvas, config):
        mock_root = MagicMock()
        mock_tk.return_value = mock_root
        
        mock_fig = MagicMock()
        mock_figure.return_value = mock_fig
        
        mock_radio = MagicMock()
        mock_radio.is_initialized.return_value = False
        mock_sim.return_value = mock_radio
        
        mock_scanner_instance = MagicMock()
        mock_scanner.return_value = mock_scanner_instance
        
        mock_mitigation_instance = MagicMock()
        mock_mitigation.return_value = mock_mitigation_instance
        
        app = SpectrumVisualizerApp(config)
        app._backend_var = MagicMock()
        app._backend_var.get.return_value = "sim"
        app._start_ch_var = MagicMock()
        app._start_ch_var.get.return_value = 0
        app._end_ch_var = MagicMock()
        app._end_ch_var.get.return_value = 5
        app._window_var = MagicMock()
        app._window_var.get.return_value = 0.1
        app._interval_var = MagicMock()
        app._interval_var.get.return_value = 10.0
        app._armed_var = MagicMock()
        app._armed_var.get.return_value = False
        app._start_btn = MagicMock()
        app._stop_btn = MagicMock()
        app._status_var = MagicMock()
        
        app._start_scanning()
        
        mock_radio.initialize.assert_called_once()
        mock_scanner_instance.start.assert_called_once()
        assert app._running is True
        app._start_btn.config.assert_called_with(state=tk.DISABLED)
        app._stop_btn.config.assert_called_with(state=tk.NORMAL)
    
    @patch('app.FigureCanvasTkAgg')
    @patch('app.Figure')
    @patch('app.tk.Tk')
    @patch('app.HardwareRadio')
    @patch('app.messagebox')
    def test_start_scanning_hardware_unavailable(self, mock_msgbox, mock_hw, mock_tk, mock_figure, mock_canvas, config):
        mock_root = MagicMock()
        mock_tk.return_value = mock_root
        
        mock_fig = MagicMock()
        mock_figure.return_value = mock_fig
        
        mock_radio = MagicMock()
        mock_radio.is_available.return_value = False
        mock_hw.return_value = mock_radio
        
        app = SpectrumVisualizerApp(config)
        app._backend_var = MagicMock()
        app._backend_var.get.return_value = "hardware"
        app._start_ch_var = MagicMock()
        app._start_ch_var.get.return_value = 0
        app._end_ch_var = MagicMock()
        app._end_ch_var.get.return_value = 5
        app._window_var = MagicMock()
        app._window_var.get.return_value = 0.1
        app._interval_var = MagicMock()
        app._interval_var.get.return_value = 10.0
        app._armed_var = MagicMock()
        app._armed_var.get.return_value = False
        
        app._start_scanning()
        
        mock_msgbox.showerror.assert_called_once()
        assert app._running is False
    
    @patch('app.FigureCanvasTkAgg')
    @patch('app.Figure')
    @patch('app.tk.Tk')
    def test_stop_scanning(self, mock_tk, mock_figure, mock_canvas, config):
        mock_root = MagicMock()
        mock_tk.return_value = mock_root
        
        mock_fig = MagicMock()
        mock_figure.return_value = mock_fig
        
        app = SpectrumVisualizerApp(config)
        app._running = True
        app._scanner = MagicMock()
        app._radio = MagicMock()
        app._refresh_job = "job123"
        app._start_btn = MagicMock()
        app._stop_btn = MagicMock()
        app._status_var = MagicMock()
        
        app._stop_scanning()
        
        app._scanner.shutdown.assert_called_once()
        app._radio.cleanup.assert_called_once()
        mock_root.after_cancel.assert_called_with("job123")
        assert app._running is False
        assert app._refresh_job is None
    
    @patch('app.FigureCanvasTkAgg')
    @patch('app.Figure')
    @patch('app.tk.Tk')
    def test_update_table(self, mock_tk, mock_figure, mock_canvas, config):
        mock_root = MagicMock()
        mock_tk.return_value = mock_root
        
        mock_fig = MagicMock()
        mock_figure.return_value = mock_fig
        
        app = SpectrumVisualizerApp(config)
        app._tree = MagicMock()
        app._tree.get_children.return_value = ["0", "1", "2"]
        
        spectrum_data = SpectrumData(config)
        for ch in range(3):
            obs = ChannelObservation(
                timestamp=1234567890.0,
                channel=ch,
                frequency_mhz=2400 + ch,
                backend="sim",
                valid_samples=100,
                rpd_positive=ch * 10,
                rpd_negative=100 - ch * 10,
                activity_percentage=float(ch * 10),
                status="Clear",
                data_sufficient=True,
                measurement_window=1.0,
                sampling_interval=0.01,
            )
            spectrum_data.update_observation(obs)
        
        app._spectrum_data = spectrum_data
        app._mitigation_engine = None
        
        app._update_table()
        
        assert app._tree.item.call_count == 3
    
    @patch('app.FigureCanvasTkAgg')
    @patch('app.Figure')
    @patch('app.tk.Tk')
    def test_make_activity_bar(self, mock_tk, mock_figure, mock_canvas, config):
        mock_root = MagicMock()
        mock_tk.return_value = mock_root
        
        mock_fig = MagicMock()
        mock_figure.return_value = mock_fig
        
        app = SpectrumVisualizerApp(config)
        
        bar = app._make_activity_bar(50.0)
        assert len(bar) == 20
        assert bar.count("█") == 10
        assert bar.count("░") == 10
        
        bar = app._make_activity_bar(None)
        assert bar == "?" * 20
        
        bar = app._make_activity_bar(0.0)
        assert bar == "░" * 20
        
        bar = app._make_activity_bar(100.0)
        assert bar == "█" * 20
    
    @patch('app.FigureCanvasTkAgg')
    @patch('app.Figure')
    @patch('app.tk.Tk')
    def test_get_status_tag(self, mock_tk, mock_figure, mock_canvas, config):
        mock_root = MagicMock()
        mock_tk.return_value = mock_root
        
        mock_fig = MagicMock()
        mock_figure.return_value = mock_fig
        
        app = SpectrumVisualizerApp(config)
        
        obs = ChannelObservation(
            timestamp=0, channel=0, frequency_mhz=2400, backend="sim",
            valid_samples=100, rpd_positive=10, rpd_negative=90,
            activity_percentage=10.0, status="Clear", data_sufficient=True,
            measurement_window=1.0, sampling_interval=0.01,
        )
        assert app._get_status_tag(obs) == "clear"
        
        obs.status = "Heavy Load"
        assert app._get_status_tag(obs) == "heavy"
        
        obs.data_sufficient = False
        assert app._get_status_tag(obs) == "insufficient"
        
        obs.error = "Some error"
        assert app._get_status_tag(obs) == "error"


class TestGUIWithoutDisplay:
    """Test that GUI can be imported without display."""
    
    def test_import_without_display(self):
        """Verify app module can be imported in headless environment."""
        import app
        assert hasattr(app, 'SpectrumVisualizerApp')
        assert hasattr(app, 'ChannelTableModel')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])