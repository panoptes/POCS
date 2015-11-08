from . import PanState


class State(PanState):

    def main(self):
        next_state = 'parking'

        self.logger.info("Getting ready! Woohoo!")

        mount = self.panoptes.observatory.mount

        try:
            mount.initialize()
            mount.unpark()
            next_state = 'scheduling'
        except Exception as e:
            self.logger.warning("Oh wait. There was a problem initializing the mount: {}".format(e))

        return next_state
