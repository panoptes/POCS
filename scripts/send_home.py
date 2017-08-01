#!/usr/bin/env python3

from pocs import POCS

pocs = POCS(simulator=['camera', 'weather'])
pocs.observatory.mount.initialize()
pocs.observatory.mount.home_and_park()
pocs.power_down()
