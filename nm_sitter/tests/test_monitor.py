"""
Tests for monitor module

Tests the CentralCameraMonitor class with mocked dependencies.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock, mock_open
from datetime import datetime
import sys
import json
import tempfile
import shutil
from pathlib import Path

# Mock zwoasi and numpy before importing modules
sys.modules['zwoasi'] = MagicMock()
sys.modules['zwoasi.zwolib'] = MagicMock()
sys.modules['numpy'] = MagicMock()

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent / "API" / "enclosures" / "central"))

from monitor import CentralCameraMonitor
from camera_interface import CameraStatus, ZWOCameraWrapper


class TestCentralCameraMonitor(unittest.TestCase):
    """Test CentralCameraMonitor class"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create temporary directory for test data
        self.test_data_dir = Path(tempfile.mkdtemp())
        
        # Mock config file
        self.test_config = {
            'central_enclosure': {
                'cameras': [
                    {'zwo_id': 0, 'friendly_name': 'Camera 1'},
                    {'zwo_id': 1, 'friendly_name': 'Camera 2'}
                ]
            }
        }
        
        # Mock the camera wrapper
        self.camera_wrapper_patcher = patch('monitor.ZWOCameraWrapper')
        self.mock_camera_wrapper_class = self.camera_wrapper_patcher.start()
        
        # Create mock camera instances
        self.mock_camera1 = MagicMock()
        self.mock_camera1.friendly_name = 'Camera 1'
        self.mock_camera1.zwo_id = 0
        self.mock_camera1.get_status.return_value = CameraStatus(
            camera_name='Camera 1',
            camera_id=0,
            timestamp=datetime.now(),
            is_online=True,
            temperature_celsius=25.0
        )
        
        self.mock_camera2 = MagicMock()
        self.mock_camera2.friendly_name = 'Camera 2'
        self.mock_camera2.zwo_id = 1
        self.mock_camera2.get_status.return_value = CameraStatus(
            camera_name='Camera 2',
            camera_id=1,
            timestamp=datetime.now(),
            is_online=True,
            temperature_celsius=24.5
        )
        
        self.mock_camera_wrapper_class.side_effect = [self.mock_camera1, self.mock_camera2]
    
    def tearDown(self):
        """Clean up after tests"""
        self.camera_wrapper_patcher.stop()
        # Clean up temporary directory
        if self.test_data_dir.exists():
            shutil.rmtree(self.test_data_dir)
    
    @patch('monitor.Path')
    @patch('builtins.open', new_callable=mock_open)
    def test_init_with_config(self, mock_file, mock_path):
        """Test monitor initialization with config file"""
        # Mock config file reading
        mock_file.return_value.read.return_value = json.dumps(self.test_config)
        
        # Mock path operations
        mock_config_path = MagicMock()
        mock_config_path.__truediv__ = lambda self, other: mock_config_path
        mock_config_path.exists.return_value = True
        mock_path.return_value.parent = mock_config_path
        
        # Mock data directory
        with patch('monitor.os.path.expanduser', return_value=str(self.test_data_dir)):
            monitor = CentralCameraMonitor(config_path="test_config.json")
        
        self.assertEqual(len(monitor.cameras), 2)
        self.assertEqual(monitor.cameras[0].friendly_name, 'Camera 1')
        self.assertEqual(monitor.cameras[1].friendly_name, 'Camera 2')
    
    @patch('monitor.Path')
    @patch('builtins.open', new_callable=mock_open)
    def test_init_no_cameras(self, mock_file, mock_path):
        """Test monitor initialization with no cameras in config"""
        empty_config = {'central_enclosure': {'cameras': []}}
        mock_file.return_value.read.return_value = json.dumps(empty_config)
        
        mock_config_path = MagicMock()
        mock_config_path.__truediv__ = lambda self, other: mock_config_path
        mock_path.return_value.parent = mock_config_path
        
        with patch('monitor.os.path.expanduser', return_value=str(self.test_data_dir)):
            monitor = CentralCameraMonitor(config_path="test_config.json")
        
        self.assertEqual(len(monitor.cameras), 0)
    
    @patch('monitor.Path')
    @patch('builtins.open', new_callable=mock_open)
    def test_add_camera(self, mock_file, mock_path):
        """Test adding a camera manually"""
        empty_config = {'central_enclosure': {'cameras': []}}
        mock_file.return_value.read.return_value = json.dumps(empty_config)
        
        mock_config_path = MagicMock()
        mock_config_path.__truediv__ = lambda self, other: mock_config_path
        mock_path.return_value.parent = mock_config_path
        
        with patch('monitor.os.path.expanduser', return_value=str(self.test_data_dir)):
            monitor = CentralCameraMonitor(config_path="test_config.json")
        
        result = monitor.add_camera(2, "Camera 3")
        self.assertTrue(result)
        self.assertEqual(len(monitor.cameras), 1)
    
    @patch('monitor.Path')
    @patch('builtins.open', new_callable=mock_open)
    def test_connect_all_cameras(self, mock_file, mock_path):
        """Test connecting to all cameras"""
        mock_file.return_value.read.return_value = json.dumps(self.test_config)
        
        mock_config_path = MagicMock()
        mock_config_path.__truediv__ = lambda self, other: mock_config_path
        mock_path.return_value.parent = mock_config_path
        
        with patch('monitor.os.path.expanduser', return_value=str(self.test_data_dir)):
            monitor = CentralCameraMonitor(config_path="test_config.json")
        
        results = monitor.connect_all_cameras()
        
        self.assertEqual(len(results), 2)
        self.mock_camera1.connect.assert_called_once()
        self.mock_camera2.connect.assert_called_once()
    
    @patch('monitor.Path')
    @patch('builtins.open', new_callable=mock_open)
    def test_get_all_statuses(self, mock_file, mock_path):
        """Test getting statuses for all cameras"""
        mock_file.return_value.read.return_value = json.dumps(self.test_config)
        
        mock_config_path = MagicMock()
        mock_config_path.__truediv__ = lambda self, other: mock_config_path
        mock_path.return_value.parent = mock_config_path
        
        with patch('monitor.os.path.expanduser', return_value=str(self.test_data_dir)):
            monitor = CentralCameraMonitor(config_path="test_config.json")
        
        statuses = monitor.get_all_statuses()
        
        self.assertEqual(len(statuses), 2)
        self.assertEqual(statuses[0].camera_name, 'Camera 1')
        self.assertEqual(statuses[1].camera_name, 'Camera 2')
    
    @patch('monitor.Path')
    @patch('builtins.open', new_callable=mock_open)
    def test_get_status_dict(self, mock_file, mock_path):
        """Test getting status dictionary"""
        mock_file.return_value.read.return_value = json.dumps(self.test_config)
        
        mock_config_path = MagicMock()
        mock_config_path.__truediv__ = lambda self, other: mock_config_path
        mock_path.return_value.parent = mock_config_path
        
        with patch('monitor.os.path.expanduser', return_value=str(self.test_data_dir)):
            monitor = CentralCameraMonitor(config_path="test_config.json")
        
        status_dict = monitor.get_status_dict()
        
        self.assertIn('Camera 1', status_dict)
        self.assertIn('Camera 2', status_dict)
        self.assertIsInstance(status_dict['Camera 1'], dict)
    
    @patch('monitor.Path')
    @patch('builtins.open', new_callable=mock_open)
    def test_check_status_all_healthy(self, mock_file, mock_path):
        """Test status check when all cameras are healthy"""
        mock_file.return_value.read.return_value = json.dumps(self.test_config)
        
        mock_config_path = MagicMock()
        mock_config_path.__truediv__ = lambda self, other: mock_config_path
        mock_path.return_value.parent = mock_config_path
        
        with patch('monitor.os.path.expanduser', return_value=str(self.test_data_dir)):
            monitor = CentralCameraMonitor(config_path="test_config.json")
        
        # Mock health summary to return healthy
        with patch.object(monitor, 'get_health_summary', return_value={'overall_healthy': True}):
            status_ok = monitor.check_status()
            self.assertTrue(status_ok)
    
    @patch('monitor.Path')
    @patch('builtins.open', new_callable=mock_open)
    def test_check_status_unhealthy(self, mock_file, mock_path):
        """Test status check when cameras are unhealthy"""
        mock_file.return_value.read.return_value = json.dumps(self.test_config)
        
        mock_config_path = MagicMock()
        mock_config_path.__truediv__ = lambda self, other: mock_config_path
        mock_path.return_value.parent = mock_config_path
        
        # Mock camera to be offline
        self.mock_camera1.get_status.return_value = CameraStatus(
            camera_name='Camera 1',
            camera_id=0,
            timestamp=datetime.now(),
            is_online=False
        )
        
        with patch('monitor.os.path.expanduser', return_value=str(self.test_data_dir)):
            monitor = CentralCameraMonitor(config_path="test_config.json")
        
        status_ok = monitor.check_status()
        self.assertFalse(status_ok)
    
    @patch('monitor.Path')
    @patch('builtins.open', new_callable=mock_open)
    @patch('monitor.json.dump')
    def test_save_status_to_json(self, mock_json_dump, mock_file, mock_path):
        """Test saving status to JSON file"""
        mock_file.return_value.read.return_value = json.dumps(self.test_config)
        
        mock_config_path = MagicMock()
        mock_config_path.__truediv__ = lambda self, other: mock_config_path
        mock_path.return_value.parent = mock_config_path
        
        with patch('monitor.os.path.expanduser', return_value=str(self.test_data_dir)):
            monitor = CentralCameraMonitor(config_path="test_config.json")
        
        monitor.save_status_to_json()
        
        # Verify JSON dump was called
        mock_json_dump.assert_called_once()
        call_args = mock_json_dump.call_args
        data = call_args[0][0]
        
        self.assertIn('timestamp', data)
        self.assertIn('statuses', data)
        self.assertIn('health', data)
    
    @patch('monitor.Path')
    @patch('builtins.open', new_callable=mock_open)
    def test_trim_old_files(self, mock_file, mock_path):
        """Test trimming old files to keep only 20 most recent"""
        mock_file.return_value.read.return_value = json.dumps(self.test_config)
        
        mock_config_path = MagicMock()
        mock_config_path.__truediv__ = lambda self, other: mock_config_path
        mock_path.return_value.parent = mock_config_path
        
        with patch('monitor.os.path.expanduser', return_value=str(self.test_data_dir)):
            monitor = CentralCameraMonitor(config_path="test_config.json")
        
        # Verify monitor is using the test directory
        self.assertEqual(str(monitor.data_dir.resolve()), str(self.test_data_dir.resolve()))
        
        # Create 25 test JSON files with different modification times
        import time
        for i in range(25):
            test_file = monitor.data_dir / f"camera_status_{i:03d}.json"
            test_file.write_text("{}")
            # Add small delay to ensure different mtimes for sorting
            time.sleep(0.01)
        
        # Verify we have 25 files before trimming
        initial_files = list(monitor.data_dir.glob("*.json"))
        self.assertEqual(len(initial_files), 25)
        
        # Call trim
        monitor._trim_old_files()
        
        # Should only have 20 files remaining
        remaining_files = list(monitor.data_dir.glob("*.json"))
        self.assertLessEqual(len(remaining_files), 20, 
                            f"Expected <= 20 files, but found {len(remaining_files)}. "
                            f"Monitor data_dir: {monitor.data_dir}")
    
    @patch('monitor.Path')
    @patch('builtins.open', new_callable=mock_open)
    def test_get_health_summary(self, mock_file, mock_path):
        """Test getting health summary"""
        mock_file.return_value.read.return_value = json.dumps(self.test_config)
        
        mock_config_path = MagicMock()
        mock_config_path.__truediv__ = lambda self, other: mock_config_path
        mock_path.return_value.parent = mock_config_path
        
        with patch('monitor.os.path.expanduser', return_value=str(self.test_data_dir)):
            monitor = CentralCameraMonitor(config_path="test_config.json")
        
        health = monitor.get_health_summary()
        
        self.assertIn('timestamp', health)
        self.assertIn('all_online', health)
        self.assertIn('overall_healthy', health)
        self.assertIn('cameras', health)
        self.assertIn('Camera 1', health['cameras'])
        self.assertIn('Camera 2', health['cameras'])
    
    @patch('monitor.Path')
    @patch('builtins.open', new_callable=mock_open)
    @patch('builtins.print')
    def test_print_status_check(self, mock_print, mock_file, mock_path):
        """Test printing status check"""
        mock_file.return_value.read.return_value = json.dumps(self.test_config)
        
        mock_config_path = MagicMock()
        mock_config_path.__truediv__ = lambda self, other: mock_config_path
        mock_path.return_value.parent = mock_config_path
        
        with patch('monitor.os.path.expanduser', return_value=str(self.test_data_dir)):
            monitor = CentralCameraMonitor(config_path="test_config.json")
        
        with patch.object(monitor, 'check_status', return_value=True):
            monitor.print_status_check()
            mock_print.assert_called()
            # Check that OK was printed
            call_args = str(mock_print.call_args)
            self.assertIn("OK", call_args)
        
        mock_print.reset_mock()
        
        with patch.object(monitor, 'check_status', return_value=False):
            monitor.print_status_check()
            mock_print.assert_called()
            # Check that FAILED was printed
            call_args = str(mock_print.call_args)
            self.assertIn("FAILED", call_args)


if __name__ == '__main__':
    unittest.main()

