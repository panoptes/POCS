import datetime
import os
import sys
import re
import time
import subprocess

from panoptes.utils import logger
from panoptes.camera import Camera


@logger.has_logger
class CanonDSLR(camera.Camera):
    def __init__(self, USB_port='usb:001,017'):
        super().__init__()
        self.logger.info('Setting up Canon DSLR camera')
        self.cooled = True
        self.model = None
        self.USB_port = USB_port

    def connect(self):
        '''
        For Canon DSLRs using gphoto2, this just means confirming that there is
        a camera on that port and that we can communicate with it.
        '''
        self.logger.info('Connecting to camera')
        command = ['sudo', 'gphoto2', '--port', self.USB_port, '--summary']
        result = subprocess.check_output(command)
        print(result)
        self.connected = True
        self.logger.info('Connected')


    def start_cooling(self):
        '''
        Cooling for the simluated camera will simply be on a timer.  The camera
        will reach cooled status after a set time period.
        '''
        self.logger.info('No camera cooling available')


    def stop_cooling(self):
        '''
        Cooling for the simluated camera will simply be on a timer.  The camera
        will reach cooled status after a set time period.
        '''
        self.logger.info('No camera cooling available')


    ##-------------------------------------------------------------------------
    ## Query/Update Methods
    ##-------------------------------------------------------------------------
    def is_cooling(self):
        '''
        '''
        pass


    def is_cooled(self):
        '''
        '''
        pass


    def is_exposing(self):
        '''
        '''
        pass



if __name__ == '__main__':
    camera = CanonDSLR(USB_port='usb:001,017')
    camera.connect()

