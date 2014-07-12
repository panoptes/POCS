#!/usr/bin/env python

import time
import panoptes

pan = panoptes.Panoptes()

# for camera in pan.observatory.cameras:
#     camera.connect()

target_ra = "{}".format(pan.observatory.sun.ra)
target_dec = "+{}".format(pan.observatory.sun.dec)

target = (target_ra, target_dec)

print(target)

# pan.observatory.mount.slew_to_coordinates(target)

# while pan.observatory.mount.is_slewing:
# 	pan.observatory.mount.check_coordinates()
# 	time.sleep(1)

# for camera in pan.observatory.cameras:
#     camera.simple_capture_and_download(1/10)

# pan.observatory.mount.serial_query('goto_home')
pan.state_machine.execute()