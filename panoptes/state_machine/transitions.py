import os
import signal
import sys
import yaml
import warnings

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

        states = kwargs['states']
        transitions = kwargs['transitions']

        # Add the park trigger to all states
        for state in states:
            if state == 'parking':
                next

            transitions.append({
                'trigger': 'park',
                'source': state,
                'dest': 'parking',
            })

        initial = kwargs.get('initial', 'parked')

        super().__init__(states=states, transitions=transitions, initial=initial, send_event=True,
                         before_state_change='enter_state', after_state_change='exit_state')

        self.logger.info("State machine created")

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
