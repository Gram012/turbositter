"""
Central Enclosure Camera Monitor

Main monitoring script for all cameras in the central enclosure.
Loads configuration from project root and provides status monitoring interface.
"""

import logging
import json
import time
import os
from pathlib import Path
from typing import List, Dict
from datetime import datetime

from camera_interface import ZWOCameraWrapper, CameraStatus

_logger = logging.getLogger(__name__)


class CentralCameraMonitor:
    """Monitor for all cameras in the central enclosure"""
    
    def __init__(self, config_path: str = "../../../config.json"):
        """Initialize the camera monitor
        
        Args:
            config_path: Path to config.json relative to this file
        """
        self.cameras: List[ZWOCameraWrapper] = []
        self.config_path = Path(__file__).parent / config_path
        self.config = None
        
        # Setup data directory for JSON files
        self.data_dir = Path(os.path.expanduser("~/website_utils/enclosure_data/central/scope_cams"))
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Load configuration
        self._load_config()
    
    def _load_config(self):
        """Load camera configuration from config.json"""
        try:
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)
            
            # Extract camera configurations
            camera_configs = self.config.get('central_enclosure', {}).get('cameras', [])
            
            if not camera_configs:
                _logger.warning("No cameras configured in config.json")
                return
            
            # Add each camera from config
            for cam_config in camera_configs:
                zwo_id = cam_config.get('zwo_id')
                name = cam_config.get('friendly_name')
                
                if zwo_id is None or not name:
                    _logger.warning(f"Invalid camera config: {cam_config}")
                    continue
                
                self.add_camera(zwo_id, name)
            
            
        except FileNotFoundError:
            _logger.error(f"Config file not found: {self.config_path}")
            raise
        except json.JSONDecodeError as e:
            _logger.error(f"Invalid JSON in config file: {e}")
            raise
        except Exception as e:
            _logger.error(f"Error loading config: {e}")
            raise
    
    def add_camera(self, zwo_id: int, friendly_name: str) -> bool:
        """Add a camera to monitor
        
        Args:
            zwo_id: ZWO camera ID (0, 1, 2, 3)
            friendly_name: Descriptive name
            
        Returns:
            True if successful, False otherwise
        """
        try:
            camera = ZWOCameraWrapper(zwo_id, friendly_name)
            self.cameras.append(camera)
            return True
        except Exception as e:
            _logger.error(f"Failed to add camera {friendly_name} (ID: {zwo_id}): {e}")
            return False
    
    def connect_all_cameras(self) -> Dict[str, bool]:
        """Attempt to connect to all configured cameras
        
        Returns:
            Dictionary mapping camera names to connection success status
        """
        results = {}
        for camera in self.cameras:
            try:
                camera.connect()
                results[camera.friendly_name] = True
            except Exception as e:
                _logger.error(f"Failed to connect to {camera.friendly_name}: {e}")
                results[camera.friendly_name] = False
        return results
    
    def disconnect_all_cameras(self):
        """Disconnect from all cameras"""
        for camera in self.cameras:
            camera.disconnect()
    
    def get_all_statuses(self) -> List[CameraStatus]:
        """Get status for all cameras
        
        Returns:
            List of CameraStatus objects
        """
        return [camera.get_status() for camera in self.cameras]
    
    def get_status_dict(self) -> Dict[str, dict]:
        """Get status for all cameras as dictionary
        
        Returns:
            Dictionary mapping camera names to status dicts
        """
        statuses = self.get_all_statuses()
        return {status.camera_name: status.to_dict() for status in statuses}
    
    def check_status(self) -> bool:
        """Check if all cameras are functioning properly
        
        Returns:
            True if all cameras are online and healthy, False otherwise
        """
        try:
            statuses = self.get_all_statuses()
            
            if not statuses:
                return False
            
            # Check if all cameras are online
            for status in statuses:
                if not status.is_online:
                    return False
            
            # Check health summary
            health = self.get_health_summary()
            return health.get('overall_healthy', False)
            
        except Exception as e:
            _logger.error(f"Status check failed: {e}")
            return False
    
    def get_health_summary(self) -> Dict[str, any]:
        """Get overall health status for all cameras
        
        Returns:
            Dictionary with health indicators for each camera and overall system
        """
        statuses = self.get_all_statuses()
        health = {
            'timestamp': datetime.now().isoformat(),
            'all_online': True,
            'all_temperatures_ok': True,
            'all_coolers_ok': True,
            'no_recent_errors': True,
            'overall_healthy': True,
            'cameras': {}
        }
        
        for status in statuses:
            cam_health = {
                'online': status.is_online,
                'temperature_ok': True,
                'cooler_ok': True,
                'no_errors': status.error_count == 0
            }
            
            if not status.is_online:
                health['all_online'] = False
                health['overall_healthy'] = False
                cam_health['temperature_ok'] = False
                cam_health['cooler_ok'] = False
            else:
                # Check temperature (threshold: 30°C)
                if status.temperature_celsius is not None and status.temperature_celsius > 30:
                    cam_health['temperature_ok'] = False
                    health['all_temperatures_ok'] = False
                    health['overall_healthy'] = False
                
                # Check cooler (threshold: 95% = struggling)
                if status.cooler_power_percent is not None and status.cooler_power_percent > 95:
                    cam_health['cooler_ok'] = False
                    health['all_coolers_ok'] = False
                    health['overall_healthy'] = False
                
                # Check errors
                if status.error_count > 0:
                    health['no_recent_errors'] = False
            
            health['cameras'][status.camera_name] = cam_health
        
        return health
    
    def print_status_check(self):
        """Print simple pass/fail status check"""
        status_ok = self.check_status()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if status_ok:
            print(f"[{timestamp}] ✓ OK")
        else:
            print(f"[{timestamp}] ✗ FAILED")
    
    def save_status_to_json(self):
        """Save all camera status data to a timestamped JSON file
        
        Creates a JSON file with timestamp in the filename and includes
        all camera status information and health summary.
        """
        try:
            # Get all status data
            status_dict = self.get_status_dict()
            health_summary = self.get_health_summary()
            
            # Combine into a single data structure
            data = {
                'timestamp': datetime.now().isoformat(),
                'statuses': status_dict,
                'health': health_summary
            }
            
            # Create timestamped filename
            timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"camera_status_{timestamp_str}.json"
            filepath = self.data_dir / filename
            
            # Write JSON file
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            
            _logger.debug(f"Saved status data to {filepath}")
            
            # Trim old files to keep only 20 most recent
            self._trim_old_files()
            
        except Exception as e:
            _logger.error(f"Failed to save status to JSON: {e}", exc_info=True)
    
    def _trim_old_files(self):
        """Keep only the 20 most recent JSON files in the data directory
        
        Deletes older files if more than 20 JSON files exist.
        """
        try:
            # Find all JSON files in the directory
            json_files = list(self.data_dir.glob("*.json"))
            
            if len(json_files) <= 20:
                return
            
            # Sort by modification time (most recent first)
            json_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            # Delete files beyond the 20 most recent
            for file_to_delete in json_files[20:]:
                try:
                    file_to_delete.unlink()
                except Exception as e:
                    _logger.warning(f"Failed to delete old file {file_to_delete.name}: {e}")
        except Exception as e:
            _logger.error(f"Failed to trim old files: {e}", exc_info=True)
    
    def monitor_loop(self, interval_seconds: int = 10):
        """Continuous monitoring loop
        
        Args:
            interval_seconds: Time between status checks
        """
        try:
            while True:
                # Save status data to timestamped JSON file
                self.save_status_to_json()
                # Print simple status check
                self.print_status_check()
                time.sleep(interval_seconds)
        except KeyboardInterrupt:
            print("\nShutting down monitor...")


def main():
    """Main entry point for camera monitoring"""
    # Setup logging - only log errors and warnings
    logging.basicConfig(
        level=logging.WARNING,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Initialize monitor (loads config automatically)
        monitor = CentralCameraMonitor()
        
        # Connect to all cameras
        connection_results = monitor.connect_all_cameras()
        
        # Check initial connection status
        all_connected = all(connection_results.values())
        if all_connected:
            print("Initialization: ✓ OK")
        else:
            print("Initialization: ✗ FAILED")
            failed_cameras = [name for name, success in connection_results.items() if not success]
            _logger.error(f"Failed to connect to cameras: {failed_cameras}")
        
        # Start continuous monitoring
        monitor.monitor_loop(interval_seconds=10)
        
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user")
    except Exception as e:
        _logger.error(f"Fatal error: {e}", exc_info=True)
        print("Fatal error - check logs for details")
    finally:
        try:
            monitor.disconnect_all_cameras()
        except Exception:
            pass


if __name__ == "__main__":
    main()