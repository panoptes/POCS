from . import PanState


class State(PanState):

    def main(self):
        next_state = 'parking'

        self.logger.info("Getting ready! Woohoo!")

        try:
            self.panoptes.observatory.scheduler.initialize()

            for cam in self.panoptes.observatory.cameras:
                cam.connect()

            self.panoptes.observatory.mount.initialize()
            self.panoptes.observatory.mount.unpark()
            next_state = 'scheduling'
        except Exception as e:
            self.logger.warning("Oh wait. There was a problem initializing the mount: {}".format(e))

        return next_state
