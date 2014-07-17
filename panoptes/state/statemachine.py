"""@package panoptes.state.statemachine
The StateMachine for the Panoptes Project. Inherits from smach (see ros.org).
"""
import smach

import panoptes.state.states as states

import panoptes.utils.logger as logger
import panoptes.utils.error as error
import panoptes.utils.config as config

@logger.has_logger
@config.has_config
class StateMachine(object):

    def __init__(self, observatory, state_table):
        """
        Initialize the StateMachine with an `Observatory`
        of the state into the `states` dict. Sets `current_state` to 'shutdown'

        @param  observatory     An instance of panoptes.observatory.Observatory
        @param  state_table     A dict() of state/transitions pairs
        """
        assert observatory is not None, self.logger.warning(
            "StateMachine requires an observatory")
        assert state_table is not None, self.logger.warning(
            "StateMachine requires a state_table")

        self.logger.info("Creating state machine")

        # Create a state machine container. The only outcome for our state machine is Parked,
        # otherwise machine keeps running
        self.sm = smach.StateMachine(outcomes=['quit'])

        # Attach the observatory to the state machine userdata
        self.observatory = observatory

        self.state_table = state_table

        # Open our state machine container
        with self.sm:

            # Build our state machien from the supplied state_table
            for state, transitions in self.state_table.items():

                instance_name = state.upper()
                state_class = getattr(states, state.title())

                smach.StateMachine.add(instance_name, state_class(
                    observatory=self.observatory), transitions=transitions)

    def execute(self):
        """
        Starts the execution of our state machine
        """
        self.logger.info("Beginning execution of state machine")
        outcome = self.sm.execute()
        return outcome
