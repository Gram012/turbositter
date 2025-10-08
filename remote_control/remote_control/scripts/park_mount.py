import requests
import json
import sys
import argparse
from pathlib import Path
import remote_control.scripts.telescope_util as util
from remote_control.configuration import CONFIGURATION

"""
parks a telescope
    'python park_mouse.py --debug=<true/false>'
"""

parser = argparse.ArgumentParser(description="script-arg-parser")
parser.add_argument("--debug", action='store_true')
args = parser.parse_args()
debug = args.debug

telescope_name = "turbo"
protocol = "http"
wk_dir = Path(__file__).parent.absolute()
session = requests.Session()

if (not debug):
    session.verify = str(CONFIGURATION / "turbo.crt")
    session.cert = str(CONFIGURATION / "popcorn.crt"), str(CONFIGURATION / "popcorn.key")
    protocol = "https"

# Load info about observatories (confusingly the file is called telescopes.json)
with open(wk_dir.parents[0] / "telescopes.json") as file:
    observatories = json.load(file)

observatory = observatories["observatories"][0] # st. paul

telescope = None
telescopes_list = observatory["telescopes"]

# check if telescope exists
for i in telescopes_list:
    if i['name'] == telescope_name:
        telescope = i
        break

if (telescope == None):
    print(f"no telescope exists with name: {telescope_name}")
    quit()

# quit if enclosure is closed
if (not util.check_enclosure_open(session, protocol, telescope)):
    print(f"Cannot park telescope '{telescope_name}', the enclosure is closed")
    exit()

util.park_telescope(session, protocol, telescope)
print(f"Telescope {telescope_name} parked successfully")
