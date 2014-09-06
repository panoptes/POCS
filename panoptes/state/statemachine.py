"""@package panoptes.state.statemachine
The StateMachine for the Panoptes Project. Inherits from smach (see ros.org).
"""
import smach
import importlib

import panoptes.state.states

import panoptes.utils.logger as logger
import panoptes.utils.error as error
import panoptes.utils.config as config


@logger.set_log_level('debug')
@logger.has_logger
@config.has_config
class StateMachine(object):

    def __init__(self, observatory, state_table):
        """
        Initialize the state machine. For PANOPTES, a state machine runs indefinitely
        so the only possible outcome is 'quit'.

        @param  observatory     An instance of panoptes.observatory.Observatory
        @param  state_table     A dict() of state/outcomes pairs
        """
        assert observatory is not None, self.logger.warning("StateMachine requires an observatory")
        assert state_table is not None, self.logger.warning("StateMachine requires a state_table")

        self.logger.info("Creating state machine")

        self.observatory = observatory
        self.state_table = state_table

        # Adjust the smach loggers
        smach.set_loggers(self.logger.info, self.logger.warning, self.logger.debug, self.logger.error)

        # Create a state machine container. The only outcome for our state
        # is 'quit' because it runs indefinitely.
        self.sm = smach.StateMachine(outcomes=['quit'])

        # Open our state machine container and build our state machine. See
        # smach documentation for explanation:
        #
        # http://wiki.ros.org/smach/Documentation#Opening_Containers_for_Construction
        with self.sm:

            # Build our state machine from the supplied state_table
            for states in self.state_table:
                for state, outcomes in states.items():

                    # Dynamically load the module
                    state_module = importlib.import_module('.{}'.format(state.lower()), 'panoptes.state.states')

                    # Get the state class from the state module
                    if hasattr(state_module, state.title()):
                        state_class = getattr(state_module, state.title())
                    else:
                        self.logger.warning("Tried to load a state class that doesn't exist: {}", state.title())
                        next

                    # Transitions are outcome:instance_name pairings that are possible for this state.
                    # Outcomes are always lowercase and instance names are uppercase.
                    transitions = {outcome.lower(): outcome.upper() for outcome in outcomes}

                    # Add the 'parking' transition to all states
                    transitions['parking'] = 'PARKING'

                    # Instance names are all upper case
                    instance_name = state.upper()

                    # If we are in the PARKED instance, add the 'quit' outcome
                    if instance_name == 'PARKED':
                        transitions['quit'] = 'quit'

                   # Create an instance of the state class. All states receive the observatory
                    state_instance = state_class(observatory=self.observatory)

                    # Add an instance of the state to our state machine, including possible transitions.
                    smach.StateMachine.add(instance_name, state_instance, transitions=transitions)

    def execute(self):
        """
        Executes the state machine, returning the possible outcomes.

        @retval   outcome   one of the outcomes of the state machine. For now this is only 'quit'.
        """
        self.logger.info("Executing state machine")

        outcome = self.sm.execute()

        self.logger.info("State machine outcome: {}".format(outcome))
        return outcome
