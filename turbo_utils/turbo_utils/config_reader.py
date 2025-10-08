import configparser
import os
import numpy as np
from pathlib import Path

def get_config(config_file="config.ini", config_dir=Path(".")):
    """! Retrieves the configuration from a file name. Searches typical locations.
    @param config_file  The name of the configuration file
    @return             The config parser or None
    """
    # attempt to read configuration from default places
    config = configparser.ConfigParser()

    locations = [Path(os.curdir), config_dir]
    for location in locations:
        config_location = location / config_file
        read_files = config.read(config_location)
        if len(read_files) > 0:
            # found a valid configuration file
            return config
    
    return None

def read_lat_lon(config_file="config.ini", config_dir=Path(".")):
    parser = get_config(config_file = config_file, config_dir = config_dir)
    if not parser:
        return None
    lat = np.deg2rad(float(parser["site_details"]["latitude"]))
    lon = np.deg2rad(float(parser["site_details"]["longitude"]))
    return (lat, lon)

def read_db_info(config_file="config.ini", config_dir=Path(".")):
    parser = get_config(config_file = config_file, config_dir = config_dir)
    if not parser:
        return None
    return parser["postgresql"]
