from . import PanState


class State(PanState):

    def main(self):
        next_state = 'parking'

        mount = self.panoptes.observatory.mount

        try:
            mount.initialize()
            mount.unpark()
            next_state = 'scheduling'
        except Exception as e:
            self.logger.warning("Problem initializing mount: {}".format(e))

        return next_state
