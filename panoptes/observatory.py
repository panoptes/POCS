#!/usr/env/python

from __future__ import division, print_function

## Import General Tools
import sys
import os
import argparse
import logging

import ephem
import datetime
import time
from  panoptes import all


class Observatory:
    ##-------------------------------------------------------------------------
    ## Observatory init method
    ##-------------------------------------------------------------------------
    def __init__(self):
        # The following items will be handled by a config file
        self.logger = utils.Logger()
        self.logger.debug('Initializing observatory.')
        self.heartbeat_filename = 'observatory.heartbeat'
    
        # Hilo, HI
        self.site = ephem.Observer()
        self.site.lat = '19:32:09.3876'
        self.site.lon = '-155:34:34.3164'
        self.site.elevation = float(3400)
        self.site.horizon = '-12'
        
        # Pressure initially set to 0.  This could be updated later.
        self.site.pressure = float(680)

        # Initializations
        self.site.date = ephem.now()
        self.sun = ephem.Sun()

        # Create default mount and cameras. Should be read in by config file
        self.mount = self.create_mount()
        self.cameras = [self.create_camera(), self.create_camera()]

    def heartbeat(self):
        """
        ##--------------------------------------
        ## Touch a file each time signaling life
        ##--------------------------------------
        """
        self.logger.debug('Touching heartbeat file')
        f = open(self.heartbeat_filename,'w')
        f.write(str(datetime.datetime.now()) + "\n")
        f.close()

    def is_dark(self):
        """
        # Need to calculate day/night for site
        # Iniital threshold 12 deg twiligh
        #self.site.date = datetime.datetime.now()
        """
        self.logger.debug('Calculating is_dark.')
        self.site.date = ephem.now()
        self.sun.compute(self.site)
        
        self.is_dark = self.sun.alt < -12
        return self.is_dark

    def create_mount(self, type='meade'):
        """
            This will create a mount object
        """    
        return panoptes.mount.Mount()

    def create_camera(self, type='rebel'):
        """
            This will create a camera object
        """    
        return panoptes.camera.Camera()