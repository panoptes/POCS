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

class Observatory:
    ##-------------------------------------------------------------------------
    ## Observatory init method
    ##-------------------------------------------------------------------------
    def __init__(self):
        # The following items will be handled by an initialization file
        self.heartbeat_filename = 'observatory.heartbeat'
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

    def heartbeat(self):
        ##--------------------------------------
        ## Touch a file each time signaling life
        ##--------------------------------------
        f = open(self.heartbeat_filename,'w')
        f.write(str(datetime.datetime.now()) + "\n")
        f.close()

    def is_dark(self):
        # Need to calculate day/night for site
        # Iniital threshold 12 deg twiligh
        #self.site.date = datetime.datetime.now()
        self.site.date = ephem.now()
        self.sun.compute(self.site)
        
        self.is_dark = self.sun.alt < -12
        return self.is_dark

    


