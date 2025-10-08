from turbo_utils.threading_control import  _run_interruptible_thread, interrupt_main_thread
import turbo_utils.tesselation_generator as tesselation_generator
from remote_control.scheduler.alerts import AlertHandler, data_path
import xml.etree.ElementTree as ET
from astropy.table import QTable
from gcn_kafka import Consumer
import astropy_healpix as ah
from pathlib import Path
import numpy as np
import requests
import datetime

wk_dir = Path(__file__).parent.absolute()


def _download_file(url):
    ''' Source: https://stackoverflow.com/questions/16694907/download-large-file-in-python-with-requests '''
    absolute_filename = wk_dir / url.split('/')[-1]
    # NOTE the stream=True parameter below
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(absolute_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192): 
                f.write(chunk)
    return absolute_filename


def _generate_fields_from_skymap(file_path):
    # Read the file
    skymap = QTable.read(file_path)
    # Delete the file
    Path(file_path).unlink()

    # Sort by probability density
    skymap.sort('PROBDENSITY', reverse=True)
    # Get the pixel area
    level, nested_index = ah.uniq_to_level_ipix(skymap['UNIQ'])
    pixel_area = ah.nside_to_pixel_area(ah.level_to_nside(level))
    # Calculate the probability of each pixel
    probabilities = pixel_area * skymap['PROBDENSITY']
    # Find the 90% cutoff
    cumprob = np.cumsum(probabilities)
    i = cumprob.searchsorted(0.9)
    level = level[:i]
    nested_index = nested_index[:i]
    probabilities = probabilities[:i]

    # Find the corresponding tesselations of those pixels
    sky_coordinates = ah.healpix_to_lonlat(nested_index, ah.level_to_nside(level), order='nested')
    sky_coordinates = np.array(sky_coordinates).transpose()
    ids, fields = tesselation_generator.find_tess_RASA11(sky_coordinates)
    ids_to_fields = dict(zip(ids, fields))

    # Sum the probabilities of the tesselations
    weights = np.bincount(ids, weights=probabilities)
    # Sort
    sorted_ids = np.argsort(weights)
    # Remove the empty tesselations that numpy added
    j = weights.searchsorted(0., side="right", sorter=sorted_ids)
    sorted_ids = sorted_ids[j:]
    # Reverse into descending order
    sorted_ids = sorted_ids[::-1]

    ra = np.array([np.rad2deg(ids_to_fields[id][0]) for id in sorted_ids])
    dec = np.array([np.rad2deg(ids_to_fields[id][1]) for id in sorted_ids])
    sorted_ids = np.array(sorted_ids, dtype=str)
    return (sorted_ids, ra, dec)

"""! Module for a LvcAlertHandler which listens and responds to LVC alerts from GCN
"""

class LvcAlertHandler(AlertHandler):
    """! LvcAlertHandler. Generates targets from a LVC event notice
    """
    def __init__(self, event, buffer, logger):
        """! Construct a LvcAlertHandler instance
        """
        super().__init__(event, buffer, logger)
    
    @_run_interruptible_thread
    def _alert_listener(self):
        """! Alert listener for the LvcAlertHandler, subscribes to several lvc notices
        """
        # Connect as a consumer (client "TURBO_Kafka")
        # Warning: don't share the client secret with others.
        
        # acquire the lock (b/c if the thread cleanup function is called while in this section, it get hung up)
        with self.thread_lock:
            consumer = Consumer(client_id='2vvouktibnc9ghg1e3ppbd4n96',
                                client_secret='1peni3v9agalojvv48i5lmnpunjs5645rtig354hjfnnp02i2bl1')

            # Subscribe to topics and receive Ground_Positions
            consumer.subscribe(['gcn.classic.voevent.LVC_RETRACTION',
                                'gcn.classic.voevent.LVC_INITIAL',
                                'gcn.classic.voevent.LVC_PRELIMINARY'])

        while True:
            # Wait for a message from GCN
            for message in consumer.consume(timeout=1):
                if message.error():
                    print(message.error())
                    continue
                self.handle_alert(message)
    

    def handle_alert(self, data):
        """! Handles the alert by parsing the xml notice, saving it,
             downloading the probability map, tiling it, and notifying the
             scheduler
        @param data             The data retrieved by catching the alert
        """

        root = ET.fromstring(data.value())

        # Remove testing alerts
        if root.attrib.get('role') != 'observation':
            return

        event_name = f'{data.topic().split(".")[-1]}_{data.offset()}'    
        # Write xml for records
        ET.ElementTree(root).write(data_path / f'{event_name}.xml')

        self.logger.info(f"Handling an Alert: {event_name}")

        # Check alert type
        type = root.find(".//Param[@name='AlertType']").attrib.get('value')
        if type == "Retraction":
            targets = []
            expiration = datetime.datetime.now()
            priority = 0
        else:

            
            terrestrial_element = root.find(".//Param[@name='Terrestrial']")
            if terrestrial_element and float(terrestrial_element.attrib.get('value')) > 0.9:
                self.logger.info("Skipping notice. Probably terrestrial source")
                return
            
            FAR_element = root.find(".//Param[@name='FAR']")
            if FAR_element and float(FAR_element.attrib.get('value')) > 1e-08:
                self.logger.info("Skipping notice. Too unlikely to be real")
                return
            
            # Find the skymap_fits parameter within the GW_SKYMAP group
            fits_url = root.find(".//Param[@name='skymap_fits']").attrib.get('value')

            # Download skymap
            file_name = _download_file(fits_url)
            self.logger.info("Downloaded skymap")

            # Generate fields from skymap
            targets = _generate_fields_from_skymap(file_name)
            self.logger.info(f"Generated targets - {len(targets[0])} targets")
            
            # Filter on localization
            localization_cutoff = 100
            BBH_element = root.find(".//Param[@name='BBH']")
            if BBH_element and float(BBH_element.attrib.get('value')) > 0.9:
                self.logger.info("Probably a BBH. Reducing localization cutoff")
                localization_cutoff = 10

            if len(targets[0]) > localization_cutoff:
                self.logger.info(f"Skipping notice. Not localized. ({len(targets[0])} targets)")
                return
            
            # Write targets for records
            with open(data_path / f'{event_name}_targets.txt', 'w') as file:
                for id, ra, dec in zip(targets[0], targets[1], targets[2]):
                    file.write(f"{id},{ra:.5f},{dec:.5f}\n")
            self.logger.info(f"Wrote targets to file")
            
            expiration = datetime.datetime.now() + datetime.timedelta(minutes=30)
            # TODO: Actual priority calculation
            priority = 1

        # Notify Scheduler
        self.schedule_buffer.name = root.find(".//Param[@name='GraceID']").attrib.get('value')
        self.schedule_buffer.targets = targets
        self.schedule_buffer.priority = priority
        self.schedule_buffer.expiration = expiration
        self.detected_event.set()
        interrupt_main_thread()
