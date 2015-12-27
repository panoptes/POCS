from . import PanState

from ...utils import error


class State(PanState):

    def main(self, event_data):

        next_state = 'park'

        image_time = 120.0

        self.panoptes.say("I'm finding exoplanets!")

        try:
            # Take a picture with each camera
            for cam in self.panoptes.observatory.cameras:
                cam.take_exposure(seconds=image_time)

            # Blank next state
            next_state = ''

        except error.InvalidCommand as e:
            self.logger.warning("{} is already running a command.".format(cam.name))
        except Exception as e:
            self.logger.warning("Problem with imaging: {}".format(e))
            self.panoptes.say("Hmm, I'm not sure what happened with that picture.")
        else:
            next_state = 'analyze'
        finally:
            return next_state
