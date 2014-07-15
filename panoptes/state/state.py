"""@package panoptes.state.state
The base State for the Panoptes Project. Inherits from smach (see ros.org).
"""
import smach

import panoptes.utils.logger as logger
import panoptes.utils.error as error

@logger.has_logger
class PanoptesState(smach.State):
    def __init__(self, outcomes=[]):
        smach.State.__init__(self, outcomes=outcomes, input_keys=['observatory_in'], output_keys=['observatory_out'])

    def execute(self, userdata):
        raise NotImplemented()        