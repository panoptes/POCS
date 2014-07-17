"""@package panoptes.state.statemachine
The StateMachine for the Panoptes Project. Inherits from smach (see ros.org).
"""
import smach

import panoptes.state.states

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

        self.observatory = observatory
        self.state_table = state_table

        # Create a state machine container. The only outcome for our state
        # is 'quit' because it runs indefinitely.
        self.sm = smach.StateMachine(outcomes=['quit'])

        # Open our state machine container and build our state machine
        with self.sm:

            # Build our state machine from the supplied state_table.
            for state, transitions in self.state_table.items():

                # Class instances are all upper case
                instance_name = state.upper()

                # Get the class object from the states module
                state_class = getattr(panoptes.states.states, state.title())

                # Create an instance of the state
                state_instance = state_class(observatory=self.observatory)

                # Add an instance of the state to our state machine, including possible transitions.
                # Transitions are outcome: instance_name pairings that are possible for this state.
                smach.StateMachine.add(instance_name, state_instance, transitions=transitions)


    def execute(self):
        """
        Executes the state machine, returning the possible outcomes. Note that because of our setup
        above, the only possible outcome for our state machine is 'quit'. This may change in the future.
        """
        self.logger.info("Beginning execution of state machine")

        outcome = self.sm.execute()

        return outcome
