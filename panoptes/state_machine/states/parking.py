from . import PanState


class State(PanState):

    def main(self):

        next_state = 'parked'

        mount = self.panoptes.observatory.mount

        try:
            if mount.is_initialized and mount.is_connected:
                self.panoptes.say("I'm takin' it on home and then parking.")
                mount.home_and_park()
        except Exception as e:
            self.panoptes.say("Yikes. Problem in parking: {}".format(e))

        return next_state
