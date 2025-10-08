from remote_control.scheduler.alerts import AlertHandler
from turbo_utils.threading_control.interruptible_timer import InterruptibleTimer

import random

"""! Module for a DummyAlert which is intended for testing the TURBO hardware Alert system
"""

class DummyAlert(AlertHandler):
    """! DummyAlert. Generates fake alerts with RA/DEC pointings for testing purposes.
    """
    def __init__(self):
        """! Construct a DummyAlert instance
        """
        super().__init__()
        ## An interruptible timer used by the DummyAlert
        self.timer = InterruptibleTimer()
    
    def _alert_listener(self):
        """! Alert listener for the DummyAlert, waits periodically before propagating an Alert
        """
        # specific alert listener (busy wait, etc.), implemented by child classes
        while True:
            # time to wait in between alerts
            wait = 60
            self.timer.sleep(wait)

            # random position (RA/DEC)
            data = {
                "ra": 20 + 10 * (2.0 * random.random() - 1.0), 
                "dec": 60 + 30 * (2.0 * random.random() - 1.0)
            }

            self.handle_alert(data)
    
    def listen(self):
        """! Listens for incoming alerts
        """
        # register our interruptible timer with the listening thread
        super().listen()
        if (self.listening_thread):
            self.listening_thread.add_interrupt_handler(self.timer)


    def handle_alert(self, data):
        """! Handles the alert
        @param data             The data retrieved by catching the alert
        """
        # specific response to the alert
        print(f"Handling an Alert: {data}")