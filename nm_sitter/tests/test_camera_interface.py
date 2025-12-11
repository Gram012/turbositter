"""
Tests for camera_interface module

Tests the ZWOCameraWrapper and CameraStatus classes with mocked hardware.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock, PropertyMock
from datetime import datetime
import sys
from pathlib import Path

# Mock zwoasi and numpy before importing camera_interface
sys.modules['zwoasi'] = MagicMock()
sys.modules['zwoasi.zwolib'] = MagicMock()
sys.modules['numpy'] = MagicMock()

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent / "API" / "enclosures" / "central"))

from camera_interface import (
    ZWOCameraWrapper,
    CameraStatus,
    ExposureState
)


class TestCameraStatus(unittest.TestCase):
    """Test CameraStatus dataclass"""
    
    def test_camera_status_creation(self):
        """Test creating a CameraStatus object"""
        now = datetime.now()
        status = CameraStatus(
            camera_name="Test Camera",
            camera_id=0,
            timestamp=now,
            is_online=True
        )
        
        self.assertEqual(status.camera_name, "Test Camera")
        self.assertEqual(status.camera_id, 0)
        self.assertEqual(status.timestamp, now)
        self.assertTrue(status.is_online)
        self.assertIsNone(status.temperature_celsius)
    
    def test_camera_status_to_dict(self):
        """Test converting CameraStatus to dictionary"""
        now = datetime.now()
        status = CameraStatus(
            camera_name="Test Camera",
            camera_id=0,
            timestamp=now,
            is_online=True,
            temperature_celsius=25.5,
            gain=100
        )
        
        data = status.to_dict()
        
        self.assertEqual(data['camera_name'], "Test Camera")
        self.assertEqual(data['camera_id'], 0)
        self.assertEqual(data['is_online'], True)
        self.assertEqual(data['temperature_celsius'], 25.5)
        self.assertEqual(data['gain'], 100)
        self.assertIsInstance(data['timestamp'], str)  # Should be ISO format string


class TestZWOCameraWrapper(unittest.TestCase):
    """Test ZWOCameraWrapper class with mocked hardware"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Reset library initialization state
        ZWOCameraWrapper._lib_initialized = False
        
        # Mock the zwoasi module
        self.asi_patcher = patch('camera_interface.asi')
        self.mock_asi = self.asi_patcher.start()
        
        # Mock library initialization
        self.mock_asi.init.return_value = None
        
        # Mock zwolib submodule
        self.mock_asi.zwolib = MagicMock()
        self.mock_asi.zwolib.ASIOpenCamera.return_value = None
        self.mock_asi.zwolib.ASIInitCamera.return_value = None
        
        # Mock exposure status constants
        self.mock_asi.ASI_EXP_IDLE = 0
        self.mock_asi.ASI_EXP_WORKING = 1
        self.mock_asi.ASI_EXP_SUCCESS = 2
        
        # Mock control constants
        self.mock_asi.ASI_TEMPERATURE = 'ASI_TEMPERATURE'
        self.mock_asi.ASI_COOLER_POWER_PERC = 'ASI_COOLER_POWER_PERC'
        self.mock_asi.ASI_GAIN = 'ASI_GAIN'
        self.mock_asi.ASI_OFFSET = 'ASI_OFFSET'
        self.mock_asi.ASI_EXPOSURE = 'ASI_EXPOSURE'
        self.mock_asi.ASI_COOLER_ON = 'ASI_COOLER_ON'
        self.mock_asi.ASI_TARGET_TEMP = 'ASI_TARGET_TEMP'
        self.mock_asi.ASI_IMG_RAW16 = 'ASI_IMG_RAW16'
        
        # Mock camera object
        self.mock_camera = MagicMock()
        self.mock_asi.Camera.return_value = self.mock_camera
        
        # Mock camera properties
        self.mock_properties = {
            'Name': 'Test Camera',
            'MaxWidth': 1920,
            'MaxHeight': 1080,
            'PixelSize': 3.8
        }
        self.mock_camera.get_camera_property.return_value = self.mock_properties
        
        # Mock control values
        def get_control_value(control):
            control_map = {
                self.mock_asi.ASI_TEMPERATURE: (255,),  # 25.5°C
                self.mock_asi.ASI_COOLER_POWER_PERC: (50,),
                self.mock_asi.ASI_GAIN: (100,),
                self.mock_asi.ASI_OFFSET: (10,),
                self.mock_asi.ASI_EXPOSURE: (1000000,),  # 1 second
            }
            return control_map.get(control, (0,))
        
        self.mock_camera.get_control_value.side_effect = get_control_value
    
    def tearDown(self):
        """Clean up after tests"""
        self.asi_patcher.stop()
        ZWOCameraWrapper._lib_initialized = False
    
    def test_init(self):
        """Test camera wrapper initialization"""
        camera = ZWOCameraWrapper(0, "Test Camera")
        
        self.assertEqual(camera.zwo_id, 0)
        self.assertEqual(camera.friendly_name, "Test Camera")
        self.assertIsNone(camera.camera)
        self.assertEqual(camera.error_count, 0)
    
    def test_connect_success(self):
        """Test successful camera connection"""
        self.mock_asi.get_num_cameras.return_value = 1
        
        camera = ZWOCameraWrapper(0, "Test Camera")
        camera.connect()
        
        self.assertIsNotNone(camera.camera)
        self.assertEqual(camera.properties, self.mock_properties)
        self.mock_asi.Camera.assert_called_once_with(0)
    
    def test_connect_no_cameras(self):
        """Test connection failure when no cameras detected"""
        self.mock_asi.get_num_cameras.return_value = 0
        
        camera = ZWOCameraWrapper(0, "Test Camera")
        
        with self.assertRaises(Exception) as context:
            camera.connect()
        
        self.assertIn("No ZWO cameras detected", str(context.exception))
    
    def test_connect_invalid_id(self):
        """Test connection failure with invalid camera ID"""
        self.mock_asi.get_num_cameras.return_value = 1
        
        camera = ZWOCameraWrapper(5, "Test Camera")
        
        with self.assertRaises(Exception) as context:
            camera.connect()
        
        self.assertIn("not available", str(context.exception))
    
    def test_is_online_true(self):
        """Test is_online returns True when camera is connected"""
        self.mock_asi.get_num_cameras.return_value = 1
        
        camera = ZWOCameraWrapper(0, "Test Camera")
        camera.connect()
        
        self.assertTrue(camera.is_online())
    
    def test_is_online_false(self):
        """Test is_online returns False when camera is not connected"""
        camera = ZWOCameraWrapper(0, "Test Camera")
        
        self.assertFalse(camera.is_online())
    
    def test_get_temperature(self):
        """Test getting camera temperature"""
        self.mock_asi.get_num_cameras.return_value = 1
        
        camera = ZWOCameraWrapper(0, "Test Camera")
        camera.connect()
        
        temp = camera.get_temperature_celsius()
        self.assertEqual(temp, 25.5)
    
    def test_get_temperature_not_connected(self):
        """Test getting temperature when camera not connected"""
        camera = ZWOCameraWrapper(0, "Test Camera")
        
        with self.assertRaises(Exception) as context:
            camera.get_temperature_celsius()
        
        self.assertIn("not connected", str(context.exception))
    
    def test_get_gain(self):
        """Test getting camera gain"""
        self.mock_asi.get_num_cameras.return_value = 1
        
        camera = ZWOCameraWrapper(0, "Test Camera")
        camera.connect()
        
        gain = camera.get_gain()
        self.assertEqual(gain, 100)
    
    def test_set_gain(self):
        """Test setting camera gain"""
        self.mock_asi.get_num_cameras.return_value = 1
        
        camera = ZWOCameraWrapper(0, "Test Camera")
        camera.connect()
        
        camera.set_gain(200)
        camera.camera.set_control_value.assert_called()
    
    def test_get_exposure_state(self):
        """Test getting exposure state"""
        self.mock_asi.get_num_cameras.return_value = 1
        self.mock_camera.get_exposure_status.return_value = self.mock_asi.ASI_EXP_IDLE
        
        camera = ZWOCameraWrapper(0, "Test Camera")
        camera.connect()
        
        state = camera.get_exposure_state()
        self.assertEqual(state, ExposureState.IDLE)
    
    def test_get_status_offline(self):
        """Test getting status when camera is offline"""
        camera = ZWOCameraWrapper(0, "Test Camera")
        
        status = camera.get_status()
        
        self.assertEqual(status.camera_name, "Test Camera")
        self.assertFalse(status.is_online)
        self.assertIsNone(status.temperature_celsius)
    
    def test_get_status_online(self):
        """Test getting status when camera is online"""
        self.mock_asi.get_num_cameras.return_value = 1
        self.mock_camera.get_exposure_status.return_value = self.mock_asi.ASI_EXP_IDLE
        
        camera = ZWOCameraWrapper(0, "Test Camera")
        camera.connect()
        
        status = camera.get_status()
        
        self.assertTrue(status.is_online)
        self.assertEqual(status.temperature_celsius, 25.5)
        self.assertEqual(status.gain, 100)
        self.assertEqual(status.camera_model, "Test Camera")
    
    def test_get_status_with_errors(self):
        """Test status includes error tracking"""
        camera = ZWOCameraWrapper(0, "Test Camera")
        # Set errors before getting status (should work even when offline)
        camera.error_count = 5
        camera.last_error = "Test error"
        
        status = camera.get_status()
        
        self.assertEqual(status.error_count, 5)
        self.assertEqual(status.last_error, "Test error")
    
    def test_safe_get_helper(self):
        """Test the _safe_get helper method"""
        self.mock_asi.get_num_cameras.return_value = 1
        
        camera = ZWOCameraWrapper(0, "Test Camera")
        camera.connect()
        
        # Test successful call
        result = camera._safe_get(lambda: 42)
        self.assertEqual(result, 42)
        
        # Test exception handling
        result = camera._safe_get(lambda: 1/0, default=0)
        self.assertEqual(result, 0)
    
    def test_disconnect(self):
        """Test disconnecting from camera"""
        self.mock_asi.get_num_cameras.return_value = 1
        
        camera = ZWOCameraWrapper(0, "Test Camera")
        camera.connect()
        camera.disconnect()
        
        self.assertIsNone(camera.camera)
        self.mock_camera.close.assert_called_once()
    
    def test_error_logging(self):
        """Test error logging and tracking"""
        camera = ZWOCameraWrapper(0, "Test Camera")
        
        # Simulate an error
        camera._log_error("Test error message")
        
        self.assertEqual(camera.error_count, 1)
        self.assertEqual(camera.last_error, "Test error message")
        self.assertEqual(len(camera.error_history), 1)


class TestExposureState(unittest.TestCase):
    """Test ExposureState enum"""
    
    def test_exposure_state_values(self):
        """Test ExposureState enum values"""
        self.assertEqual(ExposureState.IDLE.value, "idle")
        self.assertEqual(ExposureState.EXPOSING.value, "exposing")
        self.assertEqual(ExposureState.COMPLETE.value, "complete")
        self.assertEqual(ExposureState.FAILED.value, "failed")
        self.assertEqual(ExposureState.UNKNOWN.value, "unknown")


if __name__ == '__main__':
    unittest.main()

