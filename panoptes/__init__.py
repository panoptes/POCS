import ephem

import panoptes.utils.logger as logger
import panoptes.observatory as observatory

class Panoptes:
    """
    Base class for our unit. This is inherited by *every* object and is just
    used to set some base items for the application. Sets up logger, reads
    config file and starts up application.
    """
    def __init__(self):
        # Setup utils
        self.logger = logger.Logger()

        self.logger.info('Initializing observatory')
    
        # Hilo, HI
        self.site = ephem.Observer()
        self.site.lat = '19:32:09.3876'
        self.site.lon = '-155:34:34.3164'
        self.site.elevation = float(3400)
        self.site.horizon = '-12'
        
        # Pressure initially set to 0.  This could be updated later.
        self.site.pressure = float(680)

        # Static Initializations
        self.site.date = ephem.now()
        self.sun = ephem.Sun()        

        # Create our observatory, which does the bulk of the work
        # NOTE: Here we would pass in config options
        self.observatory = observatory.Observatory( logger=self.logger )
        
    def start_session(self):
        """
        Main starting point for panoptes application
        """
        self.observatory.start_observing()

if __name__ == '__main__':
    panoptes = Panoptes()
    panoptes.logger.info("Panoptes created. Starting session")
    # panoptes.start_session()        