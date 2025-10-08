# Scheduling
This package has code for scheduling the telescopes.
The scheduler runs remotely from a central computer, to coordinate observations.
Commands are sent to the telescopes via the API.
The package contains utilities to load targets, check their visibility, divide them among multiple telescopes, and send commands over the telescope API.
It is integrated with the alerts package to change behavior when a notice of an event is received.

## Usage
Ensure the telescope api is running on the central computer (control computer)
From the scheduling directory, execute

`python run_scheduler.py`

run_scheduler.py sets up all objects needed by the scheduler, including the alert handlers and the objects shared between them. 
