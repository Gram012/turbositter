import requests
import json
import argparse
import sys

# scripts to use for testing the turbo telescope in st. paul

def handle_telescope_request(request, telescope):
    """! handle api request errors
    @param request: session.request object
    @param telescope: telescope object
    """
    if (request.status_code != 200):
        print(f"ERROR: request {request.request} to telescope '{telescope['name']}' failed with status code {request.status_code}")
        exit()


def close_enclosure(session, protocol, telescope):
    """! Closes the enclosure
    """
    r = session.post(f"{protocol}://{telescope['ip']}:{telescope['port']}/direct_control/enclosure/close")
    handle_telescope_request(r, telescope)


def open_enclosure(session, protocol, telescope):
    """! Opens the enclosure
    """
    r = session.post(f"{protocol}://{telescope['ip']}:{telescope['port']}/direct_control/enclosure/open")
    handle_telescope_request(r, telescope)


def check_enclosure_open(session, protocol, telescope):
    """! Queries the enclosure. Returns true if it is all the way open
    @param session: requests.Session object
    @param protocol: API protocol (should be http)
    @param telescope: telescope to query
    @return: bool indicating if the enclosure is open
    """
    response = session.get(f"{protocol}://{telescope['ip']}:{telescope['port']}/direct_control/enclosure/is_open/")
    return response.json()["state"] == "opened"


def park_telescope(session, protocol, telescope):
    """! forces telescope to park no matter what
    @param session: requests.Session object
    @param protocol: API protocol (should be http)
    @param telescope: telescope to query
    """ 
    r = session.post(f"{protocol}://{telescope['ip']}:{telescope['port']}/telescope_controller/start")
    handle_telescope_request(r, telescope)
    r = session.post(f"{protocol}://{telescope['ip']}:{telescope['port']}/telescope_controller/reset")
    handle_telescope_request(r, telescope)
    r = session.post(f"{protocol}://{telescope['ip']}:{telescope['port']}/telescope_controller/behavior/mount/park")
    handle_telescope_request(r, telescope)


def get_enclosure_state(session, protocol, telescope):
    """! gets enclosure state
    @param session: requests.Session object
    @param protocol: API protocol (should be http)
    @param telescope: telescope withing enclosure in question
    """
    state = session.get(f"{protocol}://{telescope['ip']}:{telescope['port']}/direct_control/enclosure/get_state")
    handle_telescope_request(state, telescope)
    return state
    

def reset_controller(session, protocol, telescope):
    r = session.post(f"{protocol}://{telescope['ip']}:{telescope['port']}/telescope_controller/reset")
    handle_telescope_request(r, telescope)
    
def start_controller(session, protocol, telescope):
    r = session.post(f"{protocol}://{telescope['ip']}:{telescope['port']}/telescope_controller/start")
    handle_telescope_request(r, telescope)

def stop_controller(session, protocol, telescope):
    r = session.post(f"{protocol}://{telescope['ip']}:{telescope['port']}/telescope_controller/stop")
    handle_telescope_request(r, telescope)

