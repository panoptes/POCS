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


class Observatory( Panoptes ):
    """
    Main Observatory class
    """
    def __init__(self):
        """
        Starts up the observatory. Reads config file (TODO), sets up location,
        dates, mount, cameras, and weather station
        """

        # Create default mount and cameras. Should be read in by config file
        self.mount = self.create_mount()
        self.cameras = [self.create_camera(), self.create_camera()]
        self.weather_station = self.create_weather_station()

    def heartbeat(self):
        """
        Touch a file each time signaling life
        """
        self.logger.debug('Touching heartbeat file')
        f = open(self.heartbeat_filename,'w')
        f.write(str(datetime.datetime.now()) + "\n")
        f.close()

    def is_dark(self):
        """
        Need to calculate day/night for site
        Initial threshold 12 deg twilight
        self.site.date = datetime.datetime.now()
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

    def create_weather_station(self):
        """
        This will create a camera object
        """    
        return panoptes.weather_station