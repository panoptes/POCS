"""@package panoptes.state.mount
Holds the states for the mount
"""
import smach
import time

from panoptes.state import state

class Parked(state.PanoptesState):
    def __init__(self, observatory=None):
        assert observatory is not None
        self.observatory = observatory

        state.PanoptesState.__init__(self, outcomes=['shutdown', 'ready', 'quit'])
        self.done = False

    def execute(self, userdata):
        self.observatory.mount.check_coordinates()
        if not self.done:
            self.done = True
            return 'ready'
        else:
            return 'quit'


class Parking(state.PanoptesState):
    def __init__(self, observatory=None):
        assert observatory is not None
        self.observatory = observatory
        state.PanoptesState.__init__(self, outcomes=['parked'])

    def execute(self, userdata):
        return 'parked'


class Shutdown(state.PanoptesState):
    def __init__(self, observatory=None):
        assert observatory is not None
        self.observatory = observatory
        state.PanoptesState.__init__(self, outcomes=['sleeping'])

    def execute(self, userdata):
        return 'sleeping'


class Sleeping(state.PanoptesState):
    def __init__(self, observatory=None):
        assert observatory is not None
        self.observatory = observatory
        state.PanoptesState.__init__(self, outcomes=['parking', 'ready'])

    def execute(self, userdata):
        return 'ready'


class Ready(state.PanoptesState):
    def __init__(self, observatory=None):
        assert observatory is not None
        self.observatory = observatory
        state.PanoptesState.__init__(self, outcomes=['parking', 'scheduling'])

    def execute(self, userdata):
        return 'scheduling'


class Scheduling(state.PanoptesState):
    def __init__(self, observatory=None):
        assert observatory is not None
        self.observatory = observatory
        state.PanoptesState.__init__(self, outcomes=['parking', 'slewing'])

    def execute(self, userdata):
        self.logger.debug("WARNING!!!! Setting to track sun")

        target_ra = "{}".format(pan.observatory.sun.ra)
        target_dec = "+{}".format(pan.observatory.sun.dec)

        target = (target_ra, target_dec)

        return 'slewing'


class Slewing(state.PanoptesState):
    def __init__(self, observatory=None):
        assert observatory is not None
        self.observatory = observatory

        state.PanoptesState.__init__(self, outcomes=['parking', 'imaging'])

    def execute(self, userdata):
        target_ra = "{}".format(self.observatory.sun.ra)
        target_dec = "+{}".format(self.observatory.sun.dec)

        target = (target_ra, target_dec)

        self.observatory.mount.slew_to_coordinates(target)

        while self.observatory.mount.is_slewing:
            self.logger.info("Mount is slewing. Sleeping for two seconds...")
            time.sleep(2)

        return 'imaging'


class Imaging(state.PanoptesState):
    def __init__(self, observatory=None):
        assert observatory is not None
        self.observatory = observatory

        state.PanoptesState.__init__(self, outcomes=['parking'])

    def execute(self, userdata):
        self.logger.info("Taking a picture...")
        cam = self.observatory.cameras[0]
        cam.connect()
        cam.simple_capture_and_download(1/10)

        return 'parking'