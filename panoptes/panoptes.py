import os
import signal
import sys
import yaml

# Append the POCS dir to the system path.
pocs_dir = os.getenv('POCS', os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(pocs_dir)

from .utils.logger import has_logger
from .utils.config import load_config
from .utils.database import PanMongo

from .observatory import Observatory


@has_logger
class Panoptes(object):

    """ A Panoptes object is in charge of the entire unit.

    An instance of this object is responsible for total control
    of a PANOPTES unit. Has access to the observatory, state machine,
    a parameter server, and a messaging channel.

    Args:
        connect_on_startup: Controls whether unit should try to connect
            when object is created. Defaults to False
    """

    def __init__(self):
        # Setup utils for graceful shutdown
        signal.signal(signal.SIGINT, self._sigint_handler)

        self.logger.info('*' * 80)
        self.logger.info('Initializing PANOPTES unit')
        self._check_environment()

        self.logger.info('Checking config')
        self.config = load_config()
        self._check_config()

        # Setup the param server
        self.logger.info('Setting up database connection')
        self.db = PanMongo()

        # Create our observatory, which does the bulk of the work
        self.logger.info('Setting up observatory')
        self.observatory = Observatory()

        # self.logger.info('Loading state table')
        # self.state_table = self._load_state_table()

        # Get our state machine
        # self.logger.info('Setting up state machine')
        # self.state_machine = self._setup_state_machine()

        if self.config.get('connect_on_startup', False):
            self.logger.info('Initializing mount')
            self.observatory.mount.initialize()

    def shutdown(self):
        """ Shuts down the system

        Closes all the active threads that are listening.
        """
        self.logger.info("System is shutting down")

    def _setup_state_machine(self):
        """
        Sets up the state machine including defining all the possible states.
        """
        # Create the machine
        machine = sm.StateMachine(self.observatory, self.state_table)

        return machine

    def _load_state_table(self):
        # Get our state table
        state_table_name = self.config.get('state_machine', 'simple_state_table')

        state_table_file = "{}/resources/state_table/{}.yaml".format(self.config.get('base_dir'), state_table_name)

        state_table = dict()

        try:
            with open(state_table_file, 'r') as f:
                state_table = yaml.load(f.read())
        except OSError as err:
            raise error.InvalidConfig('Problem loading state table yaml file: {} {}'.format(err, state_table_file))
        except:
            raise error.InvalidConfig('Problem loading state table yaml file: {}'.format(state_table_file))

        return state_table

    @classmethod
    def _check_environment(cls):
        """ Checks to see if environment is set up correctly

        There are a number of environmental variables that are expected
        to be set in order for PANOPTES to work correctly. This method just
        sanity checks our environment.

            POCS    Base directory for PANOPTES
        """
        if os.getenv('POCS') is None:
            warnings.warn('Please make sure $POCS environment variable is set')
            cls.shutdown()
            sys.exit(0)

    def _check_config(self):
        """ Checks the config file for mandatory items """
        if 'name' in self.config:
            self.logger.info('Welcome {}'.format(self.config.get('name')))

        if 'base_dir' not in self.config:
            raise error.InvalidConfig('base_dir must be specified in config_local.yaml')

        if 'mount' not in self.config:
            raise error.MountNotFound('Mount must be specified in config')

        if 'state_machine' not in self.config:
            raise error.InvalidConfig('State Table must be specified in config')

    def _sigint_handler(self, signum, frame):
        """
        Interrupt signal handler. Designed to intercept a Ctrl-C from
        the user and properly shut down the system.
        """

        print("Signal handler called with signal ", signum)
        self.shutdown()
        sys.exit(0)

    def __del__(self):
        self.shutdown()

if __name__ == '__main__':
    pan = Panoptes()
