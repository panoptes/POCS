from . import PanState

from ...utils import error


class State(PanState):

    def main(self):

        image_time = 10.0

        self.logger.info("I'm finding exoplanets!")

        next_state = 'analyzing'

        mount = self.panoptes.observatory.mount

        if mount.is_tracking:

            for cam in self.panoptes.observatory.cameras:
                try:
                    cam.take_exposure(seconds=image_time)

                    while image_time:
                        image_time = image_time - 5.0
                        self.logger.info("I'm still taking a picture. Just waiting. ")
                        self.sleep(5)
                except error.InvalidCommand as e:
                    self.logger.warning("{} is already running a command.".format(cam.name))
                except Exception as e:
                    self.logger.warning("Problem with imaging: {}".format(e))

        return next_state
