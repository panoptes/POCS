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

def list_connected_cameras(logger=None):
    command = ['gphoto2', '--auto-detect']
    result = subprocess.check_output(command)
    lines = result.decode('utf-8').split('\n')
    Ports = []
    for line in lines:
        MatchCamera = re.match('([\w\d\s_\.]{30})\s(usb:\d{3},\d{3})', line)
        if MatchCamera:
            cameraname = MatchCamera.group(1).strip()
            port = MatchCamera.group(2).strip()
            if logger: logger.info('Found "{}" on port "{}"'.format(cameraname, port))
            Ports.append(port)
    return Ports