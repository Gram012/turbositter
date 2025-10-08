import pathlib
import os

PACKAGE_DIRECTORY = pathlib.Path(os.path.abspath(__file__)).parent.parent
LOGGING = (PACKAGE_DIRECTORY / "logs")
CONFIGURATION = (PACKAGE_DIRECTORY / "configuration")
