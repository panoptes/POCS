#!/usr/bin/env python

import time
import panoptes

pan = panoptes.Panoptes()

target_ra = "".format(pan.observatory.sun.ra)
target_dec = "+{}".format(pan.observatory.sun.dec)

target = (target_ra, target_dec)

pan.observatory.slew_to_coordinates(target)

while pan.observatory.mount.is_slewing:
	time.sleep(2)

pan.observatory.mount.serial_query('goto_home')

for camera in pan.observatory.cameras:
    camera.list_config()
    camera.simple_capture_and_download(1/10)

