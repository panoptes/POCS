from . import PanState

from ...utils import error


class State(PanState):

    def main(self):

        image_time = 120.0

        self.panoptes.say("I'm finding exoplanets!")

        next_state = 'analyzing'

        mount = self.panoptes.observatory.mount

        if mount.is_tracking:

            step_time = image_time / 4

            for cam in self.panoptes.observatory.cameras:
                try:
                    cam.take_exposure(seconds=image_time)
                    self.panoptes.say("I'm taking a picture for {} seconds".format(image_time))

                    while image_time:
                        image_time = image_time - step_time
                        self.sleep(step_time)
                        self.panoptes.say("I'm still taking that picture. Just waiting.")
                except error.InvalidCommand as e:
                    self.logger.warning("{} is already running a command.".format(cam.name))
                except Exception as e:
                    self.logger.warning("Problem with imaging: {}".format(e))

        return next_state
