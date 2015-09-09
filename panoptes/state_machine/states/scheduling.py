from . import PanState

class State(PanState):
    def main(self):

        next_state = 'parking'

        self.logger.info("Getting target")

        target = self.panoptes.observatory.get_target()

        if target:
            if self.panoptes.observatory.mount.set_target_coordinates(target):
                self.logger.info("Mount set to target: {}".format(target.name))
                next_state = 'slewing'
            else:
                self.logger.warning("Target not properly set")


        return next_state
