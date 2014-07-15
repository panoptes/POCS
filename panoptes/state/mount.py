"""@package panoptes.state.mount
Holds the states for the mount
"""
import smach

from panoptes.state import state

class Parked(state.PanoptesState):
    def __init__(self):
        state.PanoptesState.__init__(self, outcomes=['shutdown', 'ready', 'quit'])
        self.done = False

    def execute(self, userdata):
        userdata.observatory_in.mount.check_coordinates
        if not self.done:
            return 'ready'
        else:
            return 'quit'


class Parking(state.PanoptesState):
    def __init__(self):
        state.PanoptesState.__init__(self, outcomes=['parked'])

    def execute(self, userdata):
        return 'parked'


class Shutdown(state.PanoptesState):
    def __init__(self):
        state.PanoptesState.__init__(self, outcomes=['sleeping'])

    def execute(self, userdata):
        return 'sleeping'


class Sleeping(state.PanoptesState):
    def __init__(self):
        state.PanoptesState.__init__(self, outcomes=['parking', 'ready'])

    def execute(self, userdata):
        return 'ready'


class Ready(state.PanoptesState):
    def __init__(self):
        state.PanoptesState.__init__(self, outcomes=['parking', 'scheduling'])

    def execute(self, userdata):
        return 'scheduling'


class Scheduling(state.PanoptesState):
    def __init__(self):
        state.PanoptesState.__init__(self, outcomes=['parking', 'slewing'])

    def execute(self, userdata):
        return 'slewing'


class Slewing(state.PanoptesState):
    def __init__(self):
        state.PanoptesState.__init__(self, outcomes=['parking', 'imaging'])

    def execute(self, userdata):
        target_ra = "{}".format(userdata.observatory_in.sun.ra)
        target_dec = "+{}".format(userdata.observatory_in.sun.dec)

        target = (target_ra, target_dec)

        userdata.observatory_in.mount.slew_to_coordinates(target)

        return 'imaging'


class Imaging(state.PanoptesState):
    def __init__(self):
        state.PanoptesState.__init__(self, outcomes=['parking'])

    def execute(self, userdata):
        self.logger.info("Taking a picture...")
        cam = userdata.observatory_in.cameras[0]
        cam.connect()
        cam.simple_capture_and_download(1/10)

        return 'parking'