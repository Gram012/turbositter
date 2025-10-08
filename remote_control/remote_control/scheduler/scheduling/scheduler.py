from remote_control.configuration import CONFIGURATION
from turbo_utils.threading_control import ThreadInterrupted
from remote_control.scheduler.scheduling import scheduler_utilities as sched_utils
from turbo_utils.astronomy_utils import is_twilight
from concurrent.futures import ThreadPoolExecutor
import threading
import requests
import json
import datetime
import pickle
from pathlib import Path
from logging import Logger
import signal
import numpy as np
import time

class Schedule:
    """! Schedule class to group some data together
    """
    def __init__(self, name, targets, priority, expiration):
        """! Initializer for Schedule
        """
        ## var name
        #  A string with the name of the Schedule, should be unique
        self.name: str = name

        ## @var targets
        #  A list of targets which are comprised of ra, dec coordinates,
        #  a target name, and an exposure length
        self.targets: list = targets

        ## @var priority
        #  A int with the priority of the schedule
        self.priority: int = priority

        ## @var expiration
        #  A datetime with the expiration time of the schedule
        self.expiration: datetime.datetime = expiration

wk_dir = Path(__file__).parent.absolute()
snapshot_path = wk_dir / "data" / "event.snapshot"
FOCUS_INTERVAL = 21600 # time between next focus, in seconds. 6 hours currently
FLAT_INTERVAL = 7200 # time between flats, in seconds. 2 hours currently. (makes sure multiple flats aren't taken in the same morning/evening)
class Scheduler:
    """! Scheduler class to generate and send schedules to telescopes
    """
    def __init__(self, observatory: dict, twilight: str, hosts_file_path: str, notification: threading.Event, buffer: Schedule, logger: Logger, debug = False) -> None:
        """! Initializer for Scheduler
        """
        ## @var observatory
        #  A json dictionary with the properties of the observatory
        self.observatory: dict = observatory
        
        ## @var n_telescopes
        #  An integer with the number of telescope being scheduled
        self.n_telescopes: int = len(observatory["telescopes"])

        ## @var location
        #  A tuple with the latitude and longitude of the observatory, in radians
        self.location = (np.radians(float(observatory["latitude"])), np.radians(float(observatory["longitude"])))
        
        ## @var twilight
        #  A string with the type of twilight to wait for. 
        #  "civil"|"nautical"|"astronomical"
        self.twilight: str = twilight
        
        ## @var notification
        #  An Event for listeners to notify the scheduler of alerts
        self.notification: threading.Event = notification
        
        # Read host data from file
        host_targets = sched_utils.read_targets_from_file(hosts_file_path)

        ## @var host_schedule
        #  A Schedule with the default targets. Used when no events are ongoing
        self.host_schedule: Schedule = Schedule("Hosts", host_targets, 0, None)

        ## @var event_schedules
        #  A list of event schedules. It is sorted by priority. It is saved to
        #  a file so that events aren't lost if the Scheduler is restarted
        self.event_schedules: list[Schedule] = []

        snapshot_path.parent.mkdir(parents=False, exist_ok=True)
        if snapshot_path.is_file():
            with open(snapshot_path, "rb") as f:
                self.event_schedules = pickle.load(f)
            logger.info(f"Loaded {len(self.event_schedules)} events from snapshot")

        ## @var schedule_buffer
        #  A Schedule object which is used as a buffer for events to pass a new
        #  Schedule to the Scheduler
        self.schedule_buffer: Schedule = buffer

        ## @var current_schedules
        #  A list with lists of targets that are ready to be passed out to
        #  telescopes, as they are ready. They are sorted in order of length,
        #  so the telescope that finishes first gets the longest schedule
        self.current_schedules = []

        ## @var logger
        #  A Logger for recording activities
        self.logger: Logger = logger

        ## @var sesh
        #  A requests Session that enables one-time configuration
        self.sesh = requests.Session()

        ## @var protocol
        #  A string with the protocol name for the API. Either 'http' or 'https'
        self.protocol = "http"

        # Use TLS only if we are in the production environment
        if not debug:
            self.sesh.verify = str(CONFIGURATION/"turbo.crt")
            self.sesh.cert = (str(CONFIGURATION/"popcorn.crt"), str(CONFIGURATION/"popcorn.key"))
            self.protocol = "https"            

        ## @var keep_going
        #  A bool indicating whether the run() loop should continue
        self.keep_going = True
        
        ## @var telescope_names
        # list of telescope names
        self.telescope_names = []
        
        # get telescope names from observator to give to the auto focus manager
        self.telescope_names = [telescope['name'] for telescope in observatory["telescopes"]]

        
    def robust_http_request(self, method, url, **kwargs):
        """Perform an HTTP request with retries and error handling"""
        try:
            response = self.sesh.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            self.logger.warning(f"Request failed: {e}")
            return None

    def run(self):
        """Runs the scheduler"""
        telescopes = list(self.observatory["telescopes"])
        # Make thread pool to manage large network communications asynchronously
        thread_pool = ThreadPoolExecutor(self.n_telescopes)

        # Add signal handler for manual stop
        signal.signal(signal.SIGINT, self.sigint_handler)
        # Add signal handler for SIGTERM (sent by systemd while running as a service)
        signal.signal(signal.SIGTERM, self.sigint_handler)

        self.logger.info("Scheduler started")
        
        self.start_all_controllers()
        self.logger.info(f"Started all remote controllers ({self.n_telescopes})")
        # Send out schedules, while waiting for an event notification
        while self.keep_going:
            try:
                #Flag for if there exists an active telescopes
                is_active = False
                if not is_twilight(self.location[0],self.location[1], "civil"):
                    self.logger.debug("Not civil night. Waiting before next check.")
                    delay = 300  # Wait 5 minutes
                    self.notification.wait(delay)
                    continue
                    
                self.logger.debug(f"Polling telescopes ({self.n_telescopes})")
                #shorter delay if active telescopes: longer if non active telescopes
                
                for telescope in telescopes:
                    state = self.get_telescope_state(telescope)
                    if not state:
                        continue
                    
                    self.logger.debug(f"Telescope {telescope['name']} state: enclosure={state['enclosure']}, running={state['running']}, queue={state['queue_size']}")
                    
                    # if the enclosure is closed try to open
                    if state['enclosure'] == 'closed':
                        self.request_enclosure_open(telescope)
                        continue
                    # Wait for the enclosure to stop moving
                    elif state['enclosure'] != 'opened':
                        continue
                    
                    # If enclosure open but controller not running
                    if state['enclosure'] == 'opened' and not state['running']:
                        if self.reset_controller(telescope) and self.start_controller(telescope):
                            self.logger.info(f"Started controller for {telescope['name']}")

                    is_active = True

                    # Wait for telescope to finish queue
                    if state['queue_size'] > 0:
                        continue

                    # Take flats or wait for nautical night
                    if not is_twilight(self.location[0],self.location[1], "astronomical"):
                        if self.should_take_flats(state, telescope):
                            if self.take_flats(telescope):
                                self.logger.info(f"Sent flats request {telescope['name']}")
                        else:
                            self.logger.debug("Not nautical night.")
                        continue

                    # Focus
                    if self.should_telescope_focus(state, telescope):
                        if self.focus_telescope(telescope):
                            self.logger.info(f"Sent focus request {telescope['name']}")
                        continue
                
                    # Generate new schedules if needed
                    if len(self.current_schedules) == 0 or not self.is_still_valid(self.current_schedules[-1]):
                        if not self.generate_schedules():
                            self.logger.info("No targets visible")
                            continue
                        self.logger.info(f"Generated new schedules ({self.n_telescopes})")
                    
                    # Send schedule to telescope
                    schedule = self.current_schedules.pop()
                    self.logger.info(f"Sending schedule to {telescope['name']}: {len(schedule[0])} targets")
                    
                    if thread_pool.submit(self.send_schedule, telescope, schedule).result():
                        self.logger.info(f"Successfully sent schedule to {telescope['name']}")
                    else:
                        self.current_schedules.append(schedule)
                        self.logger.error(f"Failed to send schedule to {telescope['name']}")
                        
                delay = 15 if is_active else 60
                self.notification.wait(delay)
            except ThreadInterrupted:
                # Catch ThreadInterrupted exceptions, which are part of the notification
                pass

            if self.notification.is_set():
                self.logger.info("Event notification received")
                self.handle_notification()

        self.logger.info(f"Stopping all remote controllers ({self.n_telescopes})")
        self.stop_all_controllers()
        thread_pool.shutdown()


    def handle_notification(self):
        """! Handler for a notification received from a listner. Resets the
             controllers so they can quickly respond to the new event, adds the
             new schedule into the list and clears the notification
        """
        self.reset_all_controllers()
        self.logger.info("Reset all remote controllers")

        # Perform a 'deep' copy of the Schedule buffer
        new_schedule = Schedule(self.schedule_buffer.name,
                                self.schedule_buffer.targets,
                                self.schedule_buffer.priority,
                                self.schedule_buffer.expiration)
        self.add_event(new_schedule)

        # Regenerate all schedulers
        self.current_schedules = []

        self.notification.clear()


    def sigint_handler(self, sig, fram):
        """! Signal handler for the interrupt signal. Stops the scheduler
        """
        self.logger.info("sigint received.")
        self.stop()
        # Reset handlers to default, in case the process doesn't shut down properly
        signal.signal(signal.SIGINT, signal.default_int_handler)
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        

    def sigterm_handler(self, sig, fram):
        """! Signal handler for the interrupt signal. Stops the scheduler
        """
        self.logger.info("sigterm received.")
        self.stop()
        # Reset handlers to default, in case the process doesn't shut down properly
        signal.signal(signal.SIGINT, signal.default_int_handler)
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        

    def stop(self):
        """! Change the flag to stop the main scheduler loop. It will finish
             its current iteration.
        """
        self.logger.info("Stopping scheduler")
        self.keep_going = False
        self.notification.set()


    def generate_schedules(self) -> bool:  
        """! Uses default and event schedules to try to generated schedules for
             all the telescopes. It may fail to generate any schedules if no
             targets are visible, in which case it will return False
        @return     bool indicating whether any schedules were generated
        """
        # Clean up the event schedule list
        self.remove_expired_events()

        # Go through the events in order of priority until one is found with visible targets
        targets = ([],[],[])
        for schedule in self.event_schedules:
            targets = sched_utils.filter_for_visibility(schedule.targets, self.location, self.twilight)
            # TODO: Should this be greater than 0, like 6 or more?
            if len(targets[0]) > 0:
                break

        # Check if visible targets were found in the last step
        if len(targets[0]) == 0:
            # No visible event targets, default to host galaxies
            targets = sched_utils.filter_for_visibility(self.host_schedule.targets, self.location, self.twilight)

            if (len(targets[0]) == 0):
                self.current_schedules = []
                return False

            # Use clustering to group the targets for the telescopes
            self.current_schedules = sched_utils.separate_targets_into_clusters(targets, self.n_telescopes)

        else:
            # There were visible event targets. Divide them for the telescopes
            self.current_schedules = sched_utils.separate_targets_evenly(targets, self.n_telescopes)

        # Sort the schedule so that if lengths are uneven, the longest comes last
        self.current_schedules.sort(key=lambda x: len(x[0]))
         
        return True


    def is_still_valid(self, schedule: tuple):
        """! Checks if a schedule's targets are all currently visible
        @param schedule     The schedule to check
        @return     bool indicating whether the schedule is valid
        """
        filtered = sched_utils.filter_for_visibility(schedule, self.location, self.twilight)
        return len(schedule[0]) == len(filtered[0])


    def add_event(self, event_schedule: Schedule):
        """! Add an event schedule to the event schedules list and re-sort it
        @param event_schedule    The Schedule to add to the list
        """
        replacement = False
        for i in range(len(self.event_schedules)):
            if self.event_schedules[i].name == event_schedule.name:
                self.event_schedules[i] = event_schedule
                replacement = True
                break
        if not replacement:
            self.event_schedules.append(event_schedule)
        
        self.remove_expired_events()
        self.event_schedules.sort(reverse=True, key=lambda x: x.priority)
        self.pickle_events()


    def remove_expired_events(self):
        """! Check the expiration of all event schedules and remove the expired
             ones
        """
        for event in self.event_schedules:
            if event.expiration and event.expiration < datetime.datetime.now():
                self.event_schedules.remove(event)
        self.event_schedules.sort(reverse=True, key=lambda x: x.priority)
        self.pickle_events()


    def pickle_events(self):
        with open(snapshot_path, "wb") as f:
            pickle.dump(self.event_schedules, f)


    def get_telescope_state(self, telescope) -> bool:
        """Get the telescope state from the API."""
        try:
            response = self.robust_http_request(
                'GET',
                f"{self.protocol}://{telescope['ip']}:{telescope['port']}/telescope_controller/state"
            )
            if response:
                state = response.json()
                required_keys = ["running", "queue_size", "enclosure", "last_focused"]
                if all(key in state for key in required_keys):
                    return state
                else:
                    self.logger.error(f"Incomplete state response from {telescope['name']}")
            else:
                self.logger.error(f"No response from {telescope['name']} when requesting state")
        except json.JSONDecodeError:
            self.logger.error(f"Invalid JSON from {telescope['name']}")
        return False

    def should_telescope_focus(self, state: dict, telescope):
        """Check if telescope needs focusing based on last focus time."""
        current_time = time.time()
        last_focused = state.get('last_focused', 0)
        if last_focused > current_time:
            self.logger.warning(f"Invalid last_focused timestamp for {telescope['name']}: {last_focused}")
            return True # want to be safe and refocus the telescope
        return (current_time - last_focused) > FOCUS_INTERVAL
    
    def should_take_flats(self, state: dict, telescope) -> bool:
        """Check if telescope should take flats based on the last time they were taken."""
        current_time = time.time()
        last_flat = state.get('last_flat', 0)
        if last_flat > current_time:
            self.logger.warning(f"Invalid last_focused timestamp for {telescope['name']}: {last_flat}")
            return False # Taking flats every night isn't that important
        return (current_time - last_flat) > FLAT_INTERVAL

    def request_enclosure_open(self, telescope):
        """Request the enclosure to open. Returns true if """
        response = self.robust_http_request(
            'POST',
            f"{self.protocol}://{telescope['ip']}:{telescope['port']}/telescope_controller/enclosure/open"
        )
        if response:
            state = response.json().get('state', '')
            self.logger.info(f"Requested enclosure open for {telescope['name']}, state: {state}")
            return state in ['opened', 'opening']
        return False

    def focus_telescope(self, telescope):
        """Request the telescope to focus."""
        headers = {"Content-Type": "application/json"}
        settings = {}
        focus_url = f"{self.protocol}://{telescope['ip']}:{telescope['port']}/telescope_controller/behavior/camera/focus"
        response = self.robust_http_request('POST', focus_url, data=json.dumps(settings), headers=headers)
        return response is not None
    
    def take_flats(self, telescope):
        """Request the telescope to take flats."""
        headers = {"Content-Type": "application/json"}
        if datetime.datetime.now().hour < 12:
            flat_url = f"{self.protocol}://{telescope['ip']}:{telescope['port']}/telescope_controller/behavior/flats/dawn_flats"
            settings = {}
        else:
            flat_url = f"{self.protocol}://{telescope['ip']}:{telescope['port']}/telescope_controller/behavior/flats/dusk_flats"
            settings = {}
        response = self.robust_http_request('POST', flat_url, data=json.dumps(settings), headers=headers)
        return response is not None

    def send_schedule(self, telescope, schedule):
        """Send the schedule to the telescope controller over the API."""
        domain = f"{self.protocol}://{telescope['ip']}:{telescope['port']}"
        point_url = domain + "/telescope_controller/behavior/mount/point"
        exp_url = domain + "/telescope_controller/behavior/camera/exposure"

        headers = {"Content-Type": "application/json"}

        for i in range(len(schedule[0])):
            target = {
                "ra": schedule[1][i],
                "dec": schedule[2][i]
            }
            response_point = self.robust_http_request('POST', point_url, data=json.dumps(target), headers=headers)
            if not response_point:
                self.logger.error(f"Failed to send point command to {telescope['name']}")
                return False

            settings = {
                "exposure": 30,
                "gain": 0,
                "offset": 0,
                "frame_type": "sci",
                "object_name": schedule[0][i],
                "ra": schedule[1][i],
                "dec": schedule[2][i]
            }
            response_exp = self.robust_http_request('POST', exp_url, data=json.dumps(settings), headers=headers)
            if not response_exp:
                self.logger.error(f"Failed to send exposure command to {telescope['name']}")
                return False

        return True

    def start_controller(self, telescope):
        """Start the telescope controller."""
        response = self.robust_http_request(
            'POST',
            f"{self.protocol}://{telescope['ip']}:{telescope['port']}/telescope_controller/start"
        )
        if response:
            status = response.json().get("status")
            self.logger.info(f"Start controller response for {telescope['name']}: {status}")
            return status in ["started", "already_started"]
        else:
            self.logger.error(f"Failed to start controller for {telescope['name']}")
            return False

    def reset_controller(self, telescope):
        """Reset the telescope controller."""
        response = self.robust_http_request(
            'POST',
            f"{self.protocol}://{telescope['ip']}:{telescope['port']}/telescope_controller/reset"
        )
        if response:
            queue_size = response.json().get("queue_size")
            self.logger.info(f"Reset controller for {telescope['name']}, queue size: {queue_size}")
            return True
        else:
            self.logger.error(f"Failed to reset controller for {telescope['name']}")
            return False

    def start_all_controllers(self):
        """Start all telescope controllers."""
        for telescope in self.observatory["telescopes"]:
            self.start_controller(telescope)

    def stop_all_controllers(self):
        """Stop all telescope controllers."""
        for telescope in self.observatory["telescopes"]:
            response = self.robust_http_request(
                'POST',
                f"{self.protocol}://{telescope['ip']}:{telescope['port']}/telescope_controller/stop"
            )
            if response:
                status = response.json().get("status")
                self.logger.info(f"Stop controller response for {telescope['name']}: {status}")
            else:
                self.logger.error(f"Failed to stop controller for {telescope['name']}")

    def reset_all_controllers(self):
        """Reset all telescope controllers."""
        for telescope in self.observatory["telescopes"]:
            self.reset_controller(telescope)

    def park_telescope(self, telescope):
        """Park the telescope and return success/failure."""
        if not self.reset_controller(telescope):
            self.logger.error(f"Failed to reset controller for {telescope['name']} before parking")
            return False
            
        response = self.robust_http_request(
            'POST',
            f"{self.protocol}://{telescope['ip']}:{telescope['port']}/telescope_controller/behavior/mount/park"
        )
        if response:
            self.logger.info(f"Successfully parked telescope {telescope['name']}")
            return True
        else:
            self.logger.error(f"Failed to park telescope {telescope['name']}")
            return False