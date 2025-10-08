from remote_control.scheduler.alerts import LvcAlertHandler, FermiAlertHandler
from remote_control.scheduler.scheduling import Scheduler, Schedule
from turbo_utils.logger import setup_multilevel_logging
from logging import Logger, getLogger
from remote_control import LOGGING
import json
from pathlib import Path
import threading

wk_dir = Path(__file__).parent.absolute()

if __name__ == '__main__':
    setup_multilevel_logging(LOGGING/"scheduler")

    # Start listener threads
    logger: Logger = getLogger("listeners")
    gcn_event = threading.Event()
    schedule_buffer = Schedule(None, None, None, None)
    handlers = [LvcAlertHandler(gcn_event, schedule_buffer, logger), FermiAlertHandler(gcn_event, schedule_buffer, logger)]
    for handler in handlers:
        handler.listen()
    
    # Load info about telescopes
    with open(wk_dir.parents[1] / "telescopes.json") as file:
        telescopes = json.load(file)

    logger: Logger = getLogger("scheduler")
    
    # run scheduler on St Paul observatory
    scheduler = Scheduler(telescopes["observatories"][0], "astronomical", wk_dir / "data" / "sne_host_galaxies.txt", gcn_event, schedule_buffer, logger)
    
    try:
        scheduler.run()
    finally:
        for handler in handlers:
            try:
                # wait for handler.listen() code to stop running internally before stopping the handlers
                while (handler.thread_lock.locked()):
                    continue
                handler.stop_listening()
            except Exception as e: 
                print(e)
