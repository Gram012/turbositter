from turbo_utils.threading_control import  _run_interruptible_thread, interrupt_main_thread
from remote_control.scheduler.alerts import AlertHandler, data_path
from sklearn.neighbors import BallTree
import xml.etree.ElementTree as ET
from gcn_kafka import Consumer
import numpy as np
from pathlib import Path
import datetime

wk_dir = Path(__file__).parent.absolute()


# please just use this coordinate changer as others, such as astropy's, do
# not take/return the correct format 
def spherical_to_cartesian(spherical_cartesian_coords):
    theta = np.radians(spherical_cartesian_coords[:, 0])
    phi = np.radians(spherical_cartesian_coords[:, 1] +90)
    x = np.sin(phi) * np.cos(theta)
    y = np.sin(phi) * np.sin(theta)
    z = np.cos(phi)
    cartesian_coords = np.column_stack((x, y, z))
    return cartesian_coords

"""! Module for a FermiAlertHandler which listens and responds to Fermi alerts from GCN
"""

class FermiAlertHandler(AlertHandler):
    """! FermiAlertHandler. Generates targets from a fermi event notice
    """
    def __init__(self, event, buffer, logger):
        """! Construct a FermiAlertHandler instance
        """
        super().__init__(event, buffer, logger)

        # Read the file and extract the second and third columns
        self.tess_fields = np.loadtxt(wk_dir.parents[2] / 'configuration/RASA11.tess', usecols=(1, 2))
        # Create BallTree
        self.ball_tree = BallTree(spherical_to_cartesian(self.tess_fields), leaf_size=40)


    @_run_interruptible_thread
    def _alert_listener(self):
        """! Alert listener for the FermiAlertHandler. Subscribes to several fermi notices
        """
        # acquire lock (b/c if the thread cleanup function is called while it is in this section, it gets hung up)
        with self.thread_lock:
            # Connect as a consumer (client "TURBO_Kafka")
            # Warning: don't share the client secret with others.
            consumer = Consumer(client_id='2vvouktibnc9ghg1e3ppbd4n96',
                                client_secret='1peni3v9agalojvv48i5lmnpunjs5645rtig354hjfnnp02i2bl1')


            # Subscribe to topics and receive Ground_Positions
            # Real notices only
            # consumer.subscribe(['gcn.classic.voevent.FERMI_GBM_GND_POS'])

            # Testing included
            consumer.subscribe(['gcn.classic.voevent.FERMI_GBM_GND_POS'])
                                # 'gcn.classic.voevent.FERMI_LAT_POS_TEST'
                                # 'gcn.classic.voevent.FERMI_GBM_POS_TEST'

        while True:
            # Wait for a message from GCN
            for message in consumer.consume(timeout=1):
                if message.error():
                    self.logger.error(message.error())
                    continue

                self.handle_alert(message)


    def handle_alert(self, data):
        """! Handles the alert by parsing the xml notice, saving it, generating
             targets, and notifying the scheduler
        @param data             The data retrieved by catching the alert
        """

        # Parse the XML file
        root = ET.fromstring(data.value())
        event_name = f'{data.topic().split(".")[-1]}_{data.offset()}'

        self.logger.info(f"Handling an Alert: {event_name}")

        # Write xml for records        
        ET.ElementTree(root).write(data_path / f'{event_name}.xml')

        # Find the C1, C2, and Error2Radius elements
        error_buff = (((3.25**2) + (2.07**2))**(1/2))/2

        try:
            ra = float(root.find(".//C1").text)
            dec = float(root.find(".//C2").text)
            error = float(root.find(".//Error2Radius").text) + error_buff
        except:
            self.logger.error("ra, dec, or error element not found in the XML.")
            return

        #get everything in radians
        ra = np.radians(ra)
        dec= np.radians(dec+90)
        center = [[np.sin(dec) * np.cos(ra),np.sin(dec) * np.sin(ra),np.cos(dec)]]
        #get cartesian error radius
        r = 2*np.sin(np.radians(error)/2)

        # Query the ball tree
        field_ids = self.ball_tree.query_radius(center, r=r,sort_results=True,return_distance=True)[0][0]

        if len(field_ids) > 100:
            self.logger.info(f"Skipping notice. Not localized ({len(field_ids)} fields).")
            return
        
        # Filter the fields
        radec = self.tess_fields[field_ids]
        try:
            ra = radec[:,0]
            dec = radec[:,1]
        except Exception:
            self.logger.error(f"Could not index ra or dec: {radec}", exc_info=True)
            return
        field_ids = np.array(field_ids, dtype=str)
        targets = (field_ids, ra, dec)
        self.logger.info(f"Generated targets - {len(targets[0])} targets")

        # Write targets for records
        with open(data_path / f'{event_name}_targets.txt', 'w') as file:
            for id, ra, dec in zip(targets[0], targets[1], targets[2]):
                file.write(f"{id},{ra:.5f},{dec:.5f}\n")
        self.logger.info(f"Wrote targets to file")

        # Notify Scheduler
        self.schedule_buffer.name = root.find(".//Param[@name='TrigID']").attrib.get('value')
        self.schedule_buffer.targets = targets
        # TODO: Actual priority calculation
        self.schedule_buffer.priority = 1
        self.schedule_buffer.expiration = datetime.datetime.now() + datetime.timedelta(minutes=30)
        self.detected_event.set()
        interrupt_main_thread()
