import sys
import subprocess
import os
import pathlib

package_path = pathlib.Path(os.path.abspath(__file__)).parent.as_posix()

# enter the project directory
os.chdir(package_path)

# pip install the package
print("Pip installing the util code package")
subprocess.check_call([sys.executable, "-m", "pip", "install", "-e", "../turbo_utils"])
print("Pip installing the control code package")
subprocess.check_call([sys.executable, "-m", "pip", "install", "-e", package_path])
