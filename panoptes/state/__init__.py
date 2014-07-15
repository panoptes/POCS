"""@package panoptes.state
The StateMachine for the Panoptes Project. Inherits from smach (see ros.org).
"""
import smach

import panoptes.state.mount as mount_states

import panoptes.utils.logger as logger
import panoptes.utils.error as error

@logger.has_logger
class StateMachine(object):
    def __init__(self, observatory):
        """
        Initialize the StateMachine with an `Observatory`
        of the state into the `states` dict. Sets `current_state` to 'shutdown'

        @param  observatory     An instance of panoptes.observatory.Observatory
        """
        self.logger.info("Creating state machine")

        # Create a state machine container. The only outcome for our state machine is Parked,
        # otherwise machine keeps running
        self.sm = smach.StateMachine(outcomes=['parked', 'fail'])

        # Attach the observatory to the state machine userdata
        self.sm.userdata.observatory = observatory

        # We use a common dictonary to link the observatory between states
        remapping_dict = {
            'observatory_in': 'observatory',
            'observatory_out': 'observatory'
        }

        # Open our state machine container
        with self.sm:
            # Add states to the container
            smach.StateMachine.add('PARKED', mount_states.Parked(), transitions={'shutdown': 'SHUTDOWN'}, remapping=remapping_dict)

            smach.StateMachine.add('SHUTDOWN', mount_states.Shutdown(), transitions={'sleeping': 'SLEEPING'}, remapping=remapping_dict)

            smach.StateMachine.add('SLEEPING', mount_states.Sleeping(), transitions={'parked': 'PARKED'}, remapping=remapping_dict)


    def execute(self):
        """
        Starts the execution of our state machine
        """
        self.logger.info("Beginning execution of state machine")
        outcome = self.sm.execute()
        return outcome

@logger.has_logger
class PanoptesState(smach.State):
    def __init__(self, outcomes=[]):
        smach.State.__init__(self, outcomes=outcomes, input_keys=['observatory_in'], output_keys=['observatory_out'])

    def execute(self, userdata):
        raise NotImplemented()        