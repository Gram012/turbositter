# Camera Interface Tests

Test suite for the camera monitoring system.

## Running Tests

### Run all tests:
```bash
python -m unittest discover -s nm_sitter/tests -p "test_*.py"
```

### Run specific test file:
```bash
python -m unittest nm_sitter.tests.test_camera_interface
python -m unittest nm_sitter.tests.test_monitor
```

### Run with verbose output:
```bash
python -m unittest discover -s nm_sitter/tests -p "test_*.py" -v
```

## Test Files

- `test_camera_interface.py` - Tests for `ZWOCameraWrapper` and `CameraStatus` classes
- `test_monitor.py` - Tests for `CentralCameraMonitor` class

## Test Coverage

### Camera Interface Tests
- CameraStatus dataclass creation and serialization
- ZWOCameraWrapper initialization and connection
- Camera status retrieval (temperature, gain, exposure, etc.)
- Error handling and logging
- Exposure state management
- Safe get helper method

### Monitor Tests
- Monitor initialization with config file
- Adding and connecting cameras
- Status retrieval and health checks
- JSON file saving and trimming
- Status check output

## Notes

- Tests use mocks to avoid requiring actual ZWO camera hardware
- All hardware dependencies are mocked using `unittest.mock`
- Tests create temporary directories for file operations
- No external dependencies required beyond standard library and unittest

