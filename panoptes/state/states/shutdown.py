"""@package panoptes.state.states.shutdown

The shutdown state happens during the day, before components have been
connected.

From the shutdown state, you can go to sleeping.  This transition should be
triggered by timing.  At a user configured time, the system will connect to
components and start cooling the camera in preparation for observing.  This
time checking should be built in to this shutdown state and trigger
a transition when time is reached.

In shutdown state:
- it is:                day
- camera connected:     no
- camera cooling:       N/A
- camera cooled:        N/A
- camera exposing:      N/A
- mount connected:      no
- mount tracking:       N/A
- mount slewing:        N/A
- mount parked:         N/A
- weather:              N/A
- target chosen:        N/A
- test image taken:     N/A
- target completed:     N/A
- analysis attempted:   N/A
- analysis in progress: N/A
- astrometry solved:    N/A
- levels determined:    N/A

Timeout Condition:  This state has a timeout built in as it will end at a
given time each day.
"""

from panoptes.state import state


class Shutdown(state.PanoptesState):

    def setup(self, *args, **kwargs):
        self.outcomes = ['sleeping']
        self.wait_time = 60

    def run(self):

        self.logger.info("In shutdown state.  Waiting {} sec for dark.".format(wait_time))
        while not self.time_to_start():
            time.sleep(self.wait_time)        

        # It is past start time.  Transition to sleeping state by
        # connecting to camera and mount.
        self.logger.info("Connect to camera and mount.  Transition to sleeping.")
        try:
            # self.camera.connect()
        except:
            self.logger.critical("Unable to connect to camera.  Parking.")
            self.outcome = "parking"
        
        try:
            # self.mount.connect()
            self.outcome = "sleeping"
        except:
            self.logger.critical("Unable to connect to mount.  Parking.")
            self.outcome = "parking"

        return self.outcome


    def time_to_start(self):
        """
        Figures out if it is time to start observing or not.
        """
        return True