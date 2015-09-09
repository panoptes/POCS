from . import PanState

class State(PanState):
    def main(self):
        next_state = 'scheduling'

        mount = self.panoptes.observatory.mount

        try:
            mount.initialize()
            mount.unpark()
        except:
            self.logger.warning("Problem initializing mount")
            next_state = 'parking'

        return next_state
