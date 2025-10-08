# Scripts
## Known Errors and Issues
If you recieve error that have to do with "wrong ssl version", try running
the script with the --debug option.

The close enclosure script is not 100% safe to use yet because it does not wait for the telescope to be parked before it closes the enclosure. This is generally ok if the telescope successfully parks because the parking takes only about 15 seconds. However, if it does not park, it could damager the telescope by the doors closing on it.
## Description
The scripts here are used to control telescope and enclosure functionality remotely via the telescope controller web api.

## Usage

### !Important!
The enclosure manager currently makes these scripts pretty unusable by potentially taking control and closing the enclosure or doing some other thing every time it polls.

### close_enclosure.py
**args: [--debug OPTIONAL]**

Forces closure of a telescope enclosure.

### open_enclosure.py
**args: [--debug OPTIONAL]**

Opens a telescope enclosure.

### park_mount.py
**args: [--debug OPTIONAL]**

Forces telescope to move to its parked position.

### start_controller.py
**args: [--debug OPTIONAL]**

Starts a telescopes controller.

### stop_controller.py
**args: [--debug OPTIONAL]**

Stops a telescopes controller.

### query_enclosure.py
**args: [--debug OPTIONAL]**

Retrieves and prints telescopes enclosure status

### take_exposure.py
**args: [--debug OPTIONAL] <exposure> <gain> <frame_type> <object_name> <ra> <dec>**

Forces telescope to take an exposure according to the parameters provided in the script

### point_telescope.py
**args: [--debug OPTIONAL] <ra> <dec>**

Points telescope according to ra (right acension) and dec (declination) values

## Logic
behavioral scripts operate on a telescope as follows:

1. start the telescope controller
2. clear the telescope controller behavior queue
3. send behavior to the controller

Other scripts simply query the telescope or enclosure in some way and have no effect on behavior
