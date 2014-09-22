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

    def __init__(self, config=dict()):
        """
        Initialize the camera
        """
        self.cooled = None
        self.cooling = None

        # Create an object for just the camera config items
        self.camera_config = config if len(config) else dict()

        self.filename_pattern = self.camera_config.get('filename_pattern')



if __name__ == '__main__':
    CameraPorts = list_connected_cameras()
    Cameras = []
    for port in CameraPorts:
        Cameras.append(Camera(USB_port=port))

#     for camera in Cameras:
#         camera.load_properties()
#         camera.simple_capture_and_download(1/10)
#         sys.exit(0)
