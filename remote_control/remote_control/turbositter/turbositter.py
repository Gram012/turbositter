from remote_control.configuration import CONFIGURATION, LOGGING
from turbo_utils.astronomy_utils import is_twilight
from turbo_utils.slack import alert_slack
from turbo_utils.config_reader import read_lat_lon
import requests
import time
import logging

# Constants
POLLING_INTERVAL = 60 # 1 minute
ERROR_TIME_LIMIT = 3*60 # 3 minutes

HOST = "https://10.129.9.28:5000/"
STATE_PATH = "enclosure/get_state"
WEATHER_PATH = "weather/conditions"

# Logging config
logging.basicConfig(filename = LOGGING / "turbositter" / "turbositter.log", 
                    filemode='a',
                    format="%(asctime)s - %(name)s - %(levelname)s > %(message)s",
                    level=logging.DEBUG)

logger = logging.getLogger("TurboSitter")


def get_json(session: requests.Session, url: str) -> dict:
    """ Helper function to make request to API and handle errors
        Returns dictionary or None if there is an error      """
    try:
        response = session.get(url)
        if response.status_code == 200:
            return response.json()
        else:
            logger.warning(f"Bad status code: {response.status_code} URL: {url}")
    except requests.exceptions.ConnectionError:
        logger.warning(f"Connection Error. URL: {url}")
    except requests.exceptions.JSONDecodeError:
        logger.warning(f"Cannot Parse Json. URL: {url} ")
    except Exception as e:
        logger.warning(f"Unknown Exception: {e} URL: {url}")
    return None

def set_error_time(error_time):
    return error_time if error_time else time.time()

def run_turbositter():
    """ Main function. Forever loops checks telescope status over network and 
        sends a slack alert if a dangerous state is detected. This includes 
        losing connection. An error state must persist for a specied time
        period before a warning will be sent."""
    
    # Get the telescope location
    (lat, lon) = read_lat_lon('config.ini', CONFIGURATION)

    # Set up requests session for talking with api
    session = requests.session()
    session.verify = str(CONFIGURATION/"turbo.crt")
    session.cert = (str(CONFIGURATION/"popcorn.crt"), str(CONFIGURATION/"popcorn.key"))

    error_time = None
    error_reason = None
    weather = None
    # Monitor telescope
    logger.debug("TurboSitter started")
    while True:
        # Check error variable to see if we should send alert
        if error_time and ((time.time() - error_time) > ERROR_TIME_LIMIT):
            msg = f"TurboSitter: {error_reason}. \nNight: {is_twilight(lat, lon, 'civil')}"
            if weather:
                msg += f", No Clouds: {weather['cloudy']}, Low Wind: {weather['wind']}, No Rain: {weather['rain']}"
            else:
                msg += ". No weather data available."
            logger.info(msg)
            alert_slack(msg)
            # Reset counter
            error_time = None

        time.sleep(POLLING_INTERVAL)

        # Get state - error if None
        state = get_json(session, HOST+STATE_PATH)
        if not state:
            error_time = set_error_time(error_time)
            error_reason = "Cannot connect to enclosure"
            continue
        
        # Check if enclosure is open - No error if closed
        if state["state"] == 'closed' or state["state"] == 'closing':
            error_time = None
            continue

        # Get weather - error if None
        weather = get_json(session, HOST+WEATHER_PATH)
        if not weather:
            error_time = set_error_time(error_time)
            error_reason = "Cannot retrieve weather data"
            continue

        # Check conditions - error if bad
        if not (weather["good_conditions"] and is_twilight(lat, lon, "civil")):
            error_time = set_error_time(error_time)
            error_reason = "Bad observing conditions and enclosure still open"
            continue

        # Reset counter
        error_time = None


if __name__ == "__main__":
    run_turbositter()
    logger.debug("TurboSitter Quitting")