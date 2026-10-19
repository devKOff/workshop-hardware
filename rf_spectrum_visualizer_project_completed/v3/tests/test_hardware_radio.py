"""Unit tests for hardware radio backend (mocked)."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from hardware_radio import HardwareRadio, check_hardware_availability
from config import ChannelConfig, ScanConfig
from exceptions import (
    RadioInitializationError,
    SPIError,
    RadioNotFoundError,
    InvalidChannelError,
    HardwareError,
)


class TestHardwareRadio:
    """Tests for HardwareRadio with mocked pyrf24."""
    
    @pytest.fixture
    def config(self):
        return ChannelConfig(start_channel=0, end_channel=125)
    
    @pytest.fixture
    def scan_config(self):
        return ScanConfig(measurement_window=1.0, sampling_interval=0.01)
    
    @pytest.fixture
    def mock_pyrf24(self):
        with patch.dict('sys.modules', {'pyrf24': MagicMock()}):
            import pyrf24
            pyrf24.RF24 = MagicMock()
            pyrf24.RF24_PA_LOW = 1
            pyrf24.RF24_1MBPS = 1
            pyrf24.RF24_CRC_16 = 1
            yield pyrf24
    
    def test_is_available_without_pyrf24(self, config, scan_config):
        with patch.dict('sys.modules', {'pyrf24': None}):
            radio = HardwareRadio(config, scan_config)
            assert radio.is_available() is False
    
    def test_is_available_with_pyrf24(self, config, scan_config, mock_pyrf24):
        radio = HardwareRadio(config, scan_config)
        assert radio.is_available() is True
    
    def test_initialize_success(self, config, scan_config, mock_pyrf24):
        mock_radio = MagicMock()
        mock_radio.begin.return_value = True
        mock_pyrf24.RF24.return_value = mock_radio
        
        radio = HardwareRadio(config, scan_config)
        assert radio.initialize() is True
        assert radio.is_initialized() is True
        
        mock_radio.setPALevel.assert_called_once()
        mock_radio.setDataRate.assert_called_once()
        mock_radio.setCRCLength.assert_called_once()
        mock_radio.stopListening.assert_called_once()
        mock_radio.setChannel.assert_called_with(0)
    
    def test_initialize_failure_no_radio(self, config, scan_config, mock_pyrf24):
        mock_radio = MagicMock()
        mock_radio.begin.return_value = False
        mock_pyrf24.RF24.return_value = mock_radio
        
        radio = HardwareRadio(config, scan_config)
        with pytest.raises(RadioNotFoundError):
            radio.initialize()
    
    def test_initialize_spi_error(self, config, scan_config, mock_pyrf24):
        mock_radio = MagicMock()
        mock_radio.begin.side_effect = OSError("SPI error")
        mock_pyrf24.RF24.return_value = mock_radio
        
        radio = HardwareRadio(config, scan_config)
        with pytest.raises(SPIError):
            radio.initialize()
    
    def test_set_channel_valid(self, config, scan_config, mock_pyrf24):
        mock_radio = MagicMock()
        mock_radio.begin.return_value = True
        mock_pyrf24.RF24.return_value = mock_radio
        
        radio = HardwareRadio(config, scan_config)
        radio.initialize()
        
        radio.set_channel(50)
        assert radio.get_channel() == 50
        mock_radio.setChannel.assert_called_with(50)
    
    def test_set_channel_invalid_low(self, config, scan_config, mock_pyrf24):
        mock_radio = MagicMock()
        mock_radio.begin.return_value = True
        mock_pyrf24.RF24.return_value = mock_radio
        
        radio = HardwareRadio(config, scan_config)
        radio.initialize()
        
        with pytest.raises(InvalidChannelError):
            radio.set_channel(-1)
    
    def test_set_channel_invalid_high(self, config, scan_config, mock_pyrf24):
        mock_radio = MagicMock()
        mock_radio.begin.return_value = True
        mock_pyrf24.RF24.return_value = mock_radio
        
        radio = HardwareRadio(config, scan_config)
        radio.initialize()
        
        with pytest.raises(InvalidChannelError):
            radio.set_channel(126)
    
    def test_set_channel_not_initialized(self, config, scan_config, mock_pyrf24):
        radio = HardwareRadio(config, scan_config)
        with pytest.raises(HardwareError):
            radio.set_channel(10)
    
    def test_read_rpd(self, config, scan_config, mock_pyrf24):
        mock_radio = MagicMock()
        mock_radio.begin.return_value = True
        mock_radio.testRPD.return_value = True
        mock_pyrf24.RF24.return_value = mock_radio
        
        radio = HardwareRadio(config, scan_config)
        radio.initialize()
        
        result = radio.read_rpd()
        assert result is True
        mock_radio.testRPD.assert_called_once()
    
    def test_read_rpd_false(self, config, scan_config, mock_pyrf24):
        mock_radio = MagicMock()
        mock_radio.begin.return_value = True
        mock_radio.testRPD.return_value = False
        mock_pyrf24.RF24.return_value = mock_radio
        
        radio = HardwareRadio(config, scan_config)
        radio.initialize()
        
        result = radio.read_rpd()
        assert result is False
    
    def test_read_rpd_error(self, config, scan_config, mock_pyrf24):
        mock_radio = MagicMock()
        mock_radio.begin.return_value = True
        mock_radio.testRPD.side_effect = Exception("Read failed")
        mock_pyrf24.RF24.return_value = mock_radio
        
        radio = HardwareRadio(config, scan_config)
        radio.initialize()
        
        with pytest.raises(HardwareError):
            radio.read_rpd()
    
    def test_scan_channel(self, config, scan_config, mock_pyrf24):
        mock_radio = MagicMock()
        mock_radio.begin.return_value = True
        mock_radio.testRPD.side_effect = [True, False, True, False, True]
        mock_pyrf24.RF24.return_value = mock_radio
        
        radio = HardwareRadio(config, scan_config)
        radio.initialize()
        
        valid, positive, negative = radio.scan_channel(10, duration=0.05, interval=0.01)
        
        assert valid == 5
        assert positive == 3
        assert negative == 2
    
    def test_cleanup(self, config, scan_config, mock_pyrf24):
        mock_radio = MagicMock()
        mock_radio.begin.return_value = True
        mock_pyrf24.RF24.return_value = mock_radio
        
        radio = HardwareRadio(config, scan_config)
        radio.initialize()
        radio.cleanup()
        
        mock_radio.powerDown.assert_called_once()
        assert radio.is_initialized() is False
    
    def test_get_info(self, config, scan_config, mock_pyrf24):
        mock_radio = MagicMock()
        mock_radio.begin.return_value = True
        mock_radio.getPALevel.return_value = 1
        mock_radio.getDataRate.return_value = 1
        mock_radio.getCRCLength.return_value = 1
        mock_radio.isPVariant.return_value = True
        mock_pyrf24.RF24.return_value = mock_radio
        
        radio = HardwareRadio(config, scan_config)
        radio.initialize()
        
        info = radio.get_info()
        assert info["initialized"] is True
        assert info["channel"] == 0
        assert info["pa_level"] == 1
        assert info["is_pv"] is True


class TestCheckHardwareAvailability:
    """Tests for hardware availability check."""
    
    @patch('hardware_radio.os.path.exists')
    @patch('hardware_radio.os.access')
    def test_check_availability_no_pyrf24(self, mock_access, mock_exists):
        with patch.dict('sys.modules', {'pyrf24': None, 'spidev': None}):
            result = check_hardware_availability()
        
        assert result["pyrf24_installed"] is False
        assert result["spi_devices"] == []
        assert result["gpio_access"] is False
        assert len(result["errors"]) > 0
    
    @patch('hardware_radio.os.path.exists')
    @patch('hardware_radio.os.access')
    @patch('hardware_radio.sys.modules', {})
    def test_check_availability_with_spi(self, mock_access, mock_exists):
        mock_exists.side_effect = lambda p: p.startswith("/dev/spidev")
        mock_access.return_value = True
        
        with patch.dict('sys.modules', {
            'pyrf24': MagicMock(__version__="1.0"),
            'spidev': MagicMock(),
        }):
            import hardware_radio
            import importlib
            importlib.reload(hardware_radio)
            result = hardware_radio.check_hardware_availability()
        
        assert result["pyrf24_installed"] is True
        assert result["pyrf24_version"] == "1.0"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])