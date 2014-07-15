"""@package panoptes.state.mount
Holds the states for the mount
"""
import smach

from panoptes.state import PanoptesState

import panoptes.utils.logger as logger
import panoptes.utils.error as error

@logger.has_logger
class Parked(PanoptesState):
    def __init__(self):
        PanoptesState.__init__(self, outcomes=['shutdown', 'fail'])

    def execute(self, userdata):
        self.logger.info("Executing {}".format(type(self).__name__))
        self.logger.info("Looking at observatory lat: {}".format(userdata.observatory_in.site.lat))
        if self.counter < 3:
            self.counter += 1
            return 'shutdown'
        else:
            return 'fail'

@logger.has_logger
class Shutdown(PanoptesState):
    def __init__(self):
        PanoptesState.__init__(self, outcomes=['sleeping'])

    def execute(self, userdata):
        self.logger.info("Executing {}".format(type(self).__name__))
        return 'sleeping'

@logger.has_logger
class Sleeping(PanoptesState):
    def __init__(self):
        PanoptesState.__init__(self, outcomes=['parked'])

    def execute(self, userdata):
        self.logger.info("Executing {}".format(type(self).__name__))
        self.logger.info("Sleeping until night")
        return 'parked'
