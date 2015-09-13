from astropy.time import Time
import astropy.units as u

from . import PanState

class State(PanState):
    def main(self):

        self.logger.info("I'm finding exoplanets!")

        num_images = 2

        while num_images:
            self.logger.info("Remaining images: {}".format(num_images))
            image_time = 120

            while image_time:
                self.logger.info("Imaging for {} seconds".format(image_time))
                self.sleep(seconds=15)
                image_time = image_time - 15

            num_images = num_images - 1

        return 'analyzing'
