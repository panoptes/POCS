#!/usr/bin/env python3

from panoptes import Panoptes

pan = Panoptes(simulator=['camera', 'weather'])
pan.observatory.mount.initialize()
pan.observatory.mount.park()
pan.shutdown()
