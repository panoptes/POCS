import os
import sys
import re
import time
import datetime
import subprocess

import panoptes.utils.logger as logger
import panoptes.utils.config as config

@logger.has_logger
@config.has_config
class AbstractCamera(object):
    """
    Abstract Camera class
    """
    pass

#     def __init__(self, config=dict(), USB_port='usb:001,017', connect_on_startup=False):
#         """
#         Initialize the camera
#         """
#         # Create an object for just the mount config items
#         self.camera_config = config if len(config) else dict()
# 
#         # Get the model and port number
#         model = self.camera_config.get('model')
#         port = self.camera_config.get('port')
# 
#         # Check the config for required items
#         assert self.camera_config.get('port') is not None, self.logger.error('No mount port specified, cannot create mount\n {}'.format(self.camera_config))
# 
#         self.logger.info('Creating camera: {} {}'.format(model, port))
# 
#         self.cooled = True
#         self.cooling = False
#         self.model = model
#         self.USB_port = port
#         self.name = None
#         self.properties = None
# 
#         # Load the properties
#         if connect_on_startup: self.connect()



if __name__ == '__main__':
    CameraPorts = list_connected_cameras()
    Cameras = []
    for port in CameraPorts:
        Cameras.append(Camera(USB_port=port))

    for camera in Cameras:
        camera.load_properties()
        camera.simple_capture_and_download(1/10)
        sys.exit(0)
