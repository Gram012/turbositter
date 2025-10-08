import threading
import json
import argparse
import requests
from pathlib import Path
# from turbo_control_code.turbo_control_code.hardware.telescope.connect_to_telescope import connect_to_telescope
import remote_control.scripts.telescope_util as util
from remote_control.configuration import CONFIGURATION

# use the telescope web api to take an exposure
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

if (not util.check_enclosure_open(session, protocol, telescope)):
    print(f"Cannot take exposure, the enclosure for telescope '{telescope_name}' is closed")
    exit()

headers = {"Content-Type": "application/json"}
settings = {}
# start controller
util.start_controller(session, protocol, telescope)
# clear behavior queue
util.reset_controller(session, protocol, telescope)
r = session.post(
    f"{protocol}://{telescope['ip']}:{telescope['port']}/telescope_controller/behavior/camera/focus",
    data=json.dumps(settings), headers=headers)
util.handle_telescope_request(r, telescope)
print("Sent Focus Command")
