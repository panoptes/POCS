from . import PanState


class State(PanState):

    def main(self):

        self.logger.info("I'm finding exoplanets!")

        next_state = 'analyzing'

        mount = self.panoptes.observatory.mount

        if mount.is_tracking:
            image_time = 120.0

            for cam in self.panoptes.observatory.cameras:
                try:
                    cam.take_exposure(seconds=image_time, callback=self.process_image)
                except Exception as e:
                    self.logger.warning("Problem with imaging: {}".format(e))

        return next_state

    def process_image(self):
        """ Process the image """
        self.logger.debug("Inside imaging state process_image")
