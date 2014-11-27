"""@package panoptes.state.states
All the current PANOPTES states
"""

from panoptes.state import state

class Scheduling(state.PanoptesState):


    def setup(self, *args, **kwargs):
        self.outcomes = ['slewing']

    def run(self):
        # Get the next available target as a SkyCoord
        target = self.observatory.get_target()

        if target is not None:
            try:
                self.logger.info("Setting target {} at {}".format(target.name, target.position))
                self.observatory.mount.set_target_coordinates(target.position)
                self.outcome = 'slewing'
            except:
                self.logger.warning("Did not properly set target coordinates")
        else:
            self.outcome = 'parking'