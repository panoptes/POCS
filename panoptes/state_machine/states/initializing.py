from . import PanState

from ... utils import error


class State(PanState):

    def main(self, event_data):

        self.panoptes.say("Getting ready! Woohoo!")

        try:
            # Initialize the mount
            self.panoptes.observatory.mount.initialize()

            # If successful, unpark and slew to home.
            if self.panoptes.observatory.mount.is_initialized:
                self.panoptes.observatory.mount.unpark()

                # Slew to home
                self.panoptes.observatory.mount.slew_to_home()

                # Initialize each of the cameras while slewing
                for cam in self.panoptes.observatory.cameras:
                    cam.connect()

                # We have successfully initialized so we transition to the schedule state
                self.panoptes.schedule()
            else:
                raise error.InvalidMountCommand("Mount not initialized")

        except Exception as e:
            self.panoptes.say("Oh wait. There was a problem initializing: {}".format(e))

            # Problem, transition to park state
            self.panoptes.park()
