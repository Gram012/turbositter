"""
Camera Interface Module

Provides ZWO camera wrapper and supporting classes for status monitoring.
Self-contained interface to ZWO ASI cameras with error tracking and thread safety.
"""

import logging
import zwoasi as asi
import numpy as np
from datetime import datetime
from typing import Optional, Tuple, List
from dataclasses import dataclass, asdict
from enum import Enum
import threading

_logger = logging.getLogger(__name__)


class ExposureState(Enum):
    """Camera exposure states"""
    IDLE = "idle"
    EXPOSING = "exposing"
    COMPLETE = "complete"
    FAILED = "failed"
    UNKNOWN = "unknown"


@dataclass
class CameraStatus:
    """Complete status information for a single camera"""
    camera_name: str
    camera_id: int
    timestamp: datetime
    is_online: bool
    temperature_celsius: Optional[float] = None
    cooler_power_percent: Optional[int] = None
    gain: Optional[int] = None
    offset: Optional[int] = None
    exposure_time: Optional[float] = None
    exposure_state: str = "unknown"
    last_image_time: Optional[datetime] = None
    time_since_last_image: Optional[float] = None
    error_count: int = 0
    last_error: Optional[str] = None
    image_width: Optional[int] = None
    image_height: Optional[int] = None
    pixel_size: Optional[float] = None
    camera_model: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for easy serialization"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat() if self.timestamp else None
        data['last_image_time'] = self.last_image_time.isoformat() if self.last_image_time else None
        return data


class ZWOCameraWrapper:
    """Thread-safe wrapper for ZWO camera with status tracking"""
    
    # Class-level library initialization
    _lib_initialized = False
    _lib_lock = threading.Lock()
    
    def __init__(self, zwo_id: int, friendly_name: str):
        """Initialize camera wrapper
        
        Args:
            zwo_id: ZWO camera ID (0, 1, 2, 3, ...)
            friendly_name: Descriptive name for logging/display
        """
        self.zwo_id = zwo_id
        self.friendly_name = friendly_name
        self.camera: Optional[asi.Camera] = None
        self.properties: Optional[dict] = None
        self.hardware_lock = threading.Lock()
        
        # Status tracking attributes
        self.last_image_time: Optional[datetime] = None
        self.exposure_start_time: Optional[float] = None
        self.error_count: int = 0
        self.last_error: Optional[str] = None
        self.error_history: List[Tuple[datetime, str]] = []
        
        # Initialize library if needed
        self._init_library()
    
    @classmethod
    def _init_library(cls):
        """Initialize ZWO ASI library (one-time operation)"""
        with cls._lib_lock:
            if not cls._lib_initialized:
                try:
                    asi.init("/usr/lib/libASICamera2.so")
                    cls._lib_initialized = True
                except Exception as e:
                    _logger.error(f"Failed to initialize ZWO library: {e}")
                    raise
    
    def connect(self):
        """Connect to the camera and initialize"""
        if self.camera is not None:
            return
        
        try:
            num_cameras = asi.get_num_cameras()
            if num_cameras == 0:
                raise Exception("No ZWO cameras detected")
            
            if self.zwo_id >= num_cameras:
                raise Exception(f"Camera ID {self.zwo_id} not available (found {num_cameras} cameras)")
            
            self.camera = asi.Camera(self.zwo_id)
            
            # Initialize camera hardware
            with self.hardware_lock:
                asi.zwolib.ASIOpenCamera(self.zwo_id)
                asi.zwolib.ASIInitCamera(self.zwo_id)
                self.camera.set_image_type(asi.ASI_IMG_RAW16)
                self.properties = self.camera.get_camera_property()
            
        except Exception as e:
            self._log_error(f"Connection failed: {e}")
            raise
    
    def disconnect(self):
        """Disconnect from the camera"""
        if self.camera:
            try:
                self.camera.close()
                self.camera = None
            except Exception as e:
                _logger.error(f"Error disconnecting {self.friendly_name}: {e}")
    
    def is_online(self) -> bool:
        """Check if camera is responsive
        
        Returns:
            True if camera responds to commands, False otherwise
        """
        try:
            if self.camera:
                with self.hardware_lock:
                    self.camera.get_camera_property()
                return True
            return False
        except:
            return False
    
    def get_temperature_celsius(self) -> float:
        """Get camera temperature in Celsius
        
        Returns:
            Temperature in Celsius
        """
        if not self.camera:
            raise Exception("Camera not connected")
        
        try:
            with self.hardware_lock:
                temp_raw = self.camera.get_control_value(asi.ASI_TEMPERATURE)[0]
            return temp_raw / 10.0
        except Exception as e:
            self._log_error(f"Failed to get temperature: {e}")
            raise
    
    def get_cooler_power(self) -> int:
        """Get cooler power percentage
        
        Returns:
            Cooler power as percentage (0-100)
        """
        if not self.camera:
            raise Exception("Camera not connected")
        
        try:
            with self.hardware_lock:
                power = self.camera.get_control_value(asi.ASI_COOLER_POWER_PERC)[0]
            return power
        except Exception as e:
            self._log_error(f"Failed to get cooler power: {e}")
            raise
    
    def set_cooling(self, enabled: bool, target_temp: Optional[float] = None):
        """Enable/disable cooling and optionally set target temperature
        
        Args:
            enabled: True to enable cooling, False to disable
            target_temp: Target temperature in Celsius (if enabling)
        """
        if not self.camera:
            raise Exception("Camera not connected")
        
        try:
            with self.hardware_lock:
                self.camera.set_control_value(asi.ASI_COOLER_ON, 1 if enabled else 0)
                if enabled and target_temp is not None:
                    self.camera.set_control_value(asi.ASI_TARGET_TEMP, int(target_temp * 10.0))
        except Exception as e:
            self._log_error(f"Failed to set cooling: {e}")
            raise
    
    def get_gain(self) -> int:
        """Get camera gain setting
        
        Returns:
            Current gain value
        """
        if not self.camera:
            raise Exception("Camera not connected")
        
        try:
            with self.hardware_lock:
                gain = self.camera.get_control_value(asi.ASI_GAIN)[0]
            return gain
        except Exception as e:
            self._log_error(f"Failed to get gain: {e}")
            raise
    
    def set_gain(self, gain: int):
        """Set camera gain
        
        Args:
            gain: Gain value to set
        """
        if not self.camera:
            raise Exception("Camera not connected")
        
        try:
            with self.hardware_lock:
                self.camera.set_control_value(asi.ASI_GAIN, int(gain))
        except Exception as e:
            self._log_error(f"Failed to set gain: {e}")
            raise
    
    def get_offset(self) -> int:
        """Get camera offset setting
        
        Returns:
            Current offset value
        """
        if not self.camera:
            raise Exception("Camera not connected")
        
        try:
            with self.hardware_lock:
                offset = self.camera.get_control_value(asi.ASI_OFFSET)[0]
            return offset
        except Exception as e:
            self._log_error(f"Failed to get offset: {e}")
            raise
    
    def set_offset(self, offset: int):
        """Set camera offset
        
        Args:
            offset: Offset value to set
        """
        if not self.camera:
            raise Exception("Camera not connected")
        
        try:
            with self.hardware_lock:
                self.camera.set_control_value(asi.ASI_OFFSET, int(offset))
        except Exception as e:
            self._log_error(f"Failed to set offset: {e}")
            raise
    
    def get_exposure_time(self) -> float:
        """Get exposure time setting in seconds
        
        Returns:
            Exposure time in seconds
        """
        if not self.camera:
            raise Exception("Camera not connected")
        
        try:
            with self.hardware_lock:
                exp_us = self.camera.get_control_value(asi.ASI_EXPOSURE)[0]
            return exp_us / 1_000_000.0
        except Exception as e:
            self._log_error(f"Failed to get exposure time: {e}")
            raise
    
    def set_exposure_time(self, seconds: float):
        """Set exposure time
        
        Args:
            seconds: Exposure time in seconds
        """
        if not self.camera:
            raise Exception("Camera not connected")
        
        try:
            with self.hardware_lock:
                self.camera.set_control_value(asi.ASI_EXPOSURE, int(seconds * 1_000_000))
        except Exception as e:
            self._log_error(f"Failed to set exposure time: {e}")
            raise
    
    def get_exposure_state(self) -> ExposureState:
        """Get current exposure state
        
        Returns:
            ExposureState enum value
        """
        if not self.camera:
            return ExposureState.UNKNOWN
        
        try:
            with self.hardware_lock:
                status = self.camera.get_exposure_status()
            
            if status == asi.ASI_EXP_IDLE:
                return ExposureState.IDLE
            elif status == asi.ASI_EXP_WORKING:
                return ExposureState.EXPOSING
            elif status == asi.ASI_EXP_SUCCESS:
                return ExposureState.COMPLETE
            else:
                return ExposureState.FAILED
        except:
            return ExposureState.UNKNOWN
    
    def get_image_dimensions(self) -> Tuple[int, int]:
        """Get sensor dimensions
        
        Returns:
            Tuple of (width, height) in pixels
        """
        if not self.properties:
            raise Exception("Camera properties not available")
        
        return (self.properties.get("MaxWidth", 0), self.properties.get("MaxHeight", 0))
    
    def get_pixel_size(self) -> float:
        """Get physical pixel size
        
        Returns:
            Pixel size in microns
        """
        if not self.properties:
            raise Exception("Camera properties not available")
        
        return self.properties.get("PixelSize", 0.0)
    
    def get_camera_name(self) -> str:
        """Get camera model name
        
        Returns:
            Camera model name string
        """
        if not self.properties:
            return "Unknown"
        
        return self.properties.get("Name", "Unknown")
    
    def _safe_get(self, func, default=None):
        """Safely call a function and return default value on exception
        
        Args:
            func: Callable to execute
            default: Value to return if function raises exception
            
        Returns:
            Function result or default value
        """
        try:
            return func()
        except Exception:
            return default
    
    def get_status(self) -> CameraStatus:
        """Get complete status snapshot for this camera
        
        Returns:
            CameraStatus object with all available information
        """
        now = datetime.now()
        
        # Check if camera is online
        is_online = self.is_online()
        
        status = CameraStatus(
            camera_name=self.friendly_name,
            camera_id=self.zwo_id,
            timestamp=now,
            is_online=is_online
        )
        
        # Always include tracking attributes (even when offline)
        status.error_count = self.error_count
        status.last_error = self.last_error
        
        if not is_online:
            return status
        
        # Safely gather all status information using helper method
        status.temperature_celsius = self._safe_get(self.get_temperature_celsius)
        status.cooler_power_percent = self._safe_get(self.get_cooler_power)
        status.gain = self._safe_get(self.get_gain)
        status.offset = self._safe_get(self.get_offset)
        status.exposure_time = self._safe_get(self.get_exposure_time)
        
        # Exposure state needs special handling for enum
        exposure_state = self._safe_get(self.get_exposure_state, ExposureState.UNKNOWN)
        status.exposure_state = exposure_state.value if exposure_state else ExposureState.UNKNOWN.value
        
        # Image dimensions returns tuple
        dimensions = self._safe_get(self.get_image_dimensions)
        if dimensions:
            status.image_width, status.image_height = dimensions
        
        status.pixel_size = self._safe_get(self.get_pixel_size)
        status.camera_model = self._safe_get(self.get_camera_name)
        
        # Include tracking attributes
        if self.last_image_time:
            status.last_image_time = self.last_image_time
            status.time_since_last_image = (now - self.last_image_time).total_seconds()
        
        # Error tracking already set above (before online check)
        
        return status
    
    def _log_error(self, error_msg: str):
        """Internal method to log and track errors
        
        Args:
            error_msg: Error message to log
        """
        self.error_count += 1
        self.last_error = error_msg
        self.error_history.append((datetime.now(), error_msg))
        
        # Keep only last 100 errors
        if len(self.error_history) > 100:
            self.error_history = self.error_history[-100:]
        
        # Only log critical errors
        _logger.error(f"{self.friendly_name}: {error_msg}")
    
    def __del__(self):
        """Cleanup on deletion"""
        if self.camera:
            try:
                self.disconnect()
            except:
                pass