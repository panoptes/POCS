import os
import signal
import sys
import yaml
import warnings
import time

from transitions import Machine
from astropy.utils import resolve_name

from ..utils import *


@has_logger
class PanStateMachine(Machine):
    """ A finite state machine for PANOPTES.

    """

    def __init__(self, *args, **kwargs):
        # Setup utils for graceful shutdown
        self.logger.info("Setting up interrupt handlers for state machine")
        signal.signal(signal.SIGINT, self._sigint_handler)

        assert 'states' in kwargs, self.logger.warning('states keyword required.')
        assert 'transitions' in kwargs, self.logger.warning('transitions keyword required.')

        self.loop_delay = 5 # seconds

        self._next_state = 'initializing'
        self._prev_state = None

        self._transitions = kwargs['transitions']
        self._states = [self._load_state(state) for state in kwargs['states']]

        initial = kwargs.get('initial', 'parked')

        super().__init__(states=self._states, transitions=self._transitions, initial=initial, send_event=True,
                         before_state_change='enter_state', after_state_change='exit_state')

        self.logger.info("State machine created")


    def run(self):
        """ Runs the state machine

        Keeps the machine in a loop until the _next_state is set as 'exit'. If the
        _prev_state is the same as the _next_state, loop without doing anything.
        """

        # Loop until we receive exit.
        while self._next_state != 'exit':
            # Don't call same state over and over
            if self._next_state != self._prev_state:
                next_state = self._next_state
                to_next_state = "to_{}".format(next_state)

                # If we can call the method
                if hasattr(self, to_next_state):
                    # Call it, otherwise exit loop
                    try:
                        getattr(self, to_next_state)()
                    except TypeError:
                        self.logger.warning("Can't go to next state, parking")
                        self._next_state = 'parking'

                    # Update the previous state
                    self._prev_state = next_state
            else:
                self.logger.info("Still in {} state".format(self._next_state))
                self.logger.info("Sleeping state machine for {} seconds".format(self.loop_delay))
                time.sleep(self.loop_delay)


        self.logger.info('Next state set to exit, leaving loop')


    def enter_state(self, event_data):
        """ Called before each state """
        self.logger.info("{} called while in {} state".format(
            event_data.event.name, event_data.state.name))

    def exit_state(self, event_data):
        """ Called after each state """
        self.logger.info("Done calling {} from {}".format(
            event_data.event.name, event_data.state.name))

    @classmethod
    def load_state_table(cls, state_table_name='simple_state_table'):
        """ Loads the state table

        Args:
            state_table_name(str):  Name of state table. Corresponds to file name in
                `$POCS/resources/state_table/` directory. Default 'simple_state_table'.

        Returns:
            dict:                   Dictonary with `states` and `transitions` keys.
        """

        state_table_file = "{}/resources/state_table/{}.yaml".format(
            os.getenv('POCS'), state_table_name)

        state_table = {'states': [], 'transitions': []}

        try:
            with open(state_table_file, 'r') as f:
                state_table = yaml.load(f.read())
        except OSError as err:
            raise error.InvalidConfig(
                'Problem loading state table yaml file: {} {}'.format(err, state_table_file))
        except:
            raise error.InvalidConfig(
                'Problem loading state table yaml file: {}'.format(state_table_file))

        return state_table

##################################################################################################
# Private Methods
##################################################################################################
    def _load_state(self, state):
        self.logger.info("Loading {} state".format(state))
        state_module = load_module('panoptes.state_machine.states.{}'.format(state))

        return state_module.State(name=state)


    def _sigint_handler(self, signum, frame):
        """
        Interrupt signal handler. Designed to intercept a Ctrl-C from
        the user and properly shut down the system.
        """

        print("Signal handler called with signal ", signum)
        self.park()
        sys.exit(0)

    def __del__(self):
        pass
