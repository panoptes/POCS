import os
import signal
import sys
import yaml
import warnings

from transitions import Machine

from ..utils.logger import has_logger


@has_logger
class PanStateMachine(Machine):
    """ A finite state machine for PANOPTES

    """

    def __init__(self, *args, **kwargs):
        # Setup utils for graceful shutdown
        self.logger.info("Setting up interrupt handlers for state machine")
        signal.signal(signal.SIGINT, self._sigint_handler)

        super().__init__(*args, **kwargs)
        self.logger.info("State machine created")

    def _sigint_handler(self, signum, frame):
        """
        Interrupt signal handler. Designed to intercept a Ctrl-C from
        the user and properly shut down the system.
        """

        print("Signal handler called with signal ", signum)
        self.park()
        sys.exit(0)

    def _load_state_table(self):
        """ Loads the state table from the config """
        state_table_name = self.config.get('state_machine', 'simple_state_table')

        state_table_file = "{}/resources/state_table/{}.yaml".format(
            self.config.get('base_dir'), state_table_name)

        state_table = dict()

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

    def __del__(self):
        self.park()
