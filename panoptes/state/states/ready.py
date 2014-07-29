"""@package panoptes.state.states.ready

The getting ready state happens while it is dark, it checks if we are ready
to observe.

From the getting ready state, you can go to parking and scheduling.

In the getting ready state:
- it is:                night
- camera connected:     yes
- camera cooling:       on
- camera cooled:        no
- camera exposing:      no
- mount connected:      yes
- mount tracking:       no
- mount slewing:        no
- mount parked:         N/A
- weather:              safe
- target chosen:        no
- test image taken:     N/A
- target completed:     N/A
- analysis attempted:   N/A
- analysis in progress: N/A
- astrometry solved:    N/A
- levels determined:    N/A

To transition to the scheduling state the camera must reach the cooled
condition.

Timeout Condition:  There should be a reasonable timeout on this state.  The
timeout period should be set such that the camera can go from ambient to
cooled within the timeout period.  The state should only timeout under
extreme circumstances as the cooling process should monitor whether the
target temperature is reachable and adjust the camera set point higher if
needed and this may need time to iterate and settle down to operating temp.
If a timeout occurs, the system should go to parking state.
"""

from panoptes.state import state

class Ready(state.PanoptesState):

    def setup(self, *args, **kwargs):
        self.outcomes = ['scheduling']

    def run(self):
        # If camera is cooled, move to scheduling.
        if self.camera.cooled and self.weather.safe:
            try:
                # self.observatory.get_target()
                self.outcome = "scheduling"
            except:
                self.outcome = "ready"
                self.logger.warning("Scheduler failed to get a target.  Going back to getting ready state.")

        return self.outcome