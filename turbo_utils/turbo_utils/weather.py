import requests

def get_weather_conditions(url="http://localhost:5003/weather/conditions") -> dict:
    """ Requests current weather conditions from the weather API. Returns None
        if there is an error.
       @return  dictionary OR None
       
        The returned dictionary has the following dictionary keys:
            - forecast
            - interior_temp
            - outside_temp
            - pressure
            - wind_speed
            - wind_direction
            - interior_humidity
            - exterior_humidity
            - vantage_rain
            - aag_rain
            - light
            - ir_temp
            - time
                - Time of measurement, as given by time.time()
            - good_conditions
                - True means safe
            - wind
                - True means safe
            - rain
                - True means safe
            - cloudy
                - True means safe
       """
    try:
        response = requests.get(url)
        conditions = response.json()
    except (requests.exceptions.ConnectionError, requests.JSONDecodeError):
        conditions = None
    return conditions    
