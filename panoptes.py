#!/usr/bin/env python

import panoptes.utils as utils

class Panoptes():
    """
    Base class for our unit. This is inherited by *every* object and is just
    used to set some base items for the application. Sets up logger, reads
    config file and starts up application.
    """
    def __init__():
        # The following items will be handled by a config file
        self.logger = utils.Logger()
        self.logger.debug('Initializing observatory.')
    
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

        self.observatory = panoptes.observatory.Observatory()
        
    def start_session(self):
        """
        Main starting point for panoptes application
        """
        self.observatory.start_observing()

def query_conditions():
    observatory.weather.get_condition()  ## populates observatory.weather.safe
    observatory.camera.is_connected()    ## populates observatory.camera.connected
    observatory.camera.is_cooling()      ## populates observatory.camera.cooling
    observatory.camera.is_cooled()       ## populates observatory.camera.cooled
    observatory.camera.is_exposing()     ## populates observatory.camera.exposing
    observatory.mount.is_connected()     ## populates observatory.mount.connected
    observatory.mount.is_tracking()      ## populates observatory.mount.tracking
    observatory.mount.is_slewing()       ## populates observatory.mount.slewing
    observatory.mount.is_parked()        ## populates observatory.mount.parked


def main():
    
    states = {
              'shutdown':while_shutdown,
              'sleeping':while_sleeping,
              'getting ready':while_getting_ready,
              'scheduling':while_scheduling,
              'slewing':while_slewing,
              'taking test image':while_taking_test_image,
              'analyzing':while_analyzing,
              'imaging':while_imaging,
              'parking':while_parking,
              'parked':while_parked,
             }

    ## Operations Loop
    currentState = 'shutdown'  # assume we are in shutdown on program startup
    while True:
        query_conditions()
        thingtoexectute = states[currentState]
        currentState = thingtoexectute(observatory)

if __name__ == '__main__':
    panoptes = Panoptes()
    panoptes.logger.info("Panoptes created. Starting session")
    panoptes.start_session()