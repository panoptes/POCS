#!/usr/bin/env python3

from pocs import hardware
from pocs.core import POCS

pocs = POCS(simulator=hardware.get_all_names(without=['mount', 'night']))
pocs.observatory.mount.initialize()
pocs.observatory.mount.home_and_park()
pocs.power_down()
