from astropy.time import Time
import astropy.units as u

from . import PanState

class State(PanState):
    def main(self):

        self.logger.info("I'm finding exoplanets!")

        next_state = 'analyzing'

        mount = self.panoptes.observatory.mount

        if mount.is_tracking:
            image_time = 120

            while image_time:
                self.logger.info("Imaging for {} seconds".format(image_time))
                self.sleep(seconds=15)
                image_time = image_time - 15

        return next_state
