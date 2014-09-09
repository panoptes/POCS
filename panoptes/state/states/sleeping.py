"""@package panoptes.state.states.sleeping

The sleeping state happens during the day, after components have been
connected, while we are waiting for darkness.

From the sleeping state you can go to parking and getting ready.  Moving to
parking state should be triggered by bad weather.  Moving to getting ready
state should be triggered by timing.  At a user configured time (i.e. at
the end of twilight), the system will go to getting ready.

In sleeping state:
- it is:                day
- camera connected:     yes
- camera cooling:       no
- camera cooled:        N/A
- camera exposing:      no
- mount connected:      yes
- mount tracking:       no
- mount slewing:        no
- mount parked:         yes
- weather:              N/A
- target chosen:        N/A
- test image taken:     N/A
- target completed:     N/A
- analysis attempted:   N/A
- analysis in progress: N/A
- astrometry solved:    N/A
- levels determined:    N/A

Timeout Condition:  This state does not have a formal timeout, but should
check to see if it is night as this state should not happen during night.
"""

from panoptes.state import state

class Sleeping(state.PanoptesState):

    def setup(self, *args, **kwargs):
        self.outcomes = ['ready']

    def run(self):

        try:
            self.logger.info("Turning on camera cooler.")
            # self.camera.set_cooling(True)
            self.outcome = 'ready'
        except:
            self.logger.critical("Camera not responding to set cooling.  Parking.")

        self.logger.info("Conditions are now dark, moving to getting ready state.")
        return self.outcome