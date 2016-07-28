#!/usr/bin/env python3

from pocs import POCS

pocs = POCS(simulator=['camera', 'weather'])
pocs.observatory.mount.initialize()
pocs.observatory.mount.park()
pocs.power_down()
