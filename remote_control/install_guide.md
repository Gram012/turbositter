# Installation

## Conda Environment
`conda create -n remote_control python=3.8`

`conda activate remote_control`

## TURBO Remote Control
`python3 install.py`. This will install the dependencies for you.

## Installing the service
Copy `remote_control/services/telescope_scheduler.service` to `/etc/systemd/system`

Then run `sudo systemctl enable telescope_scheduler.service`

