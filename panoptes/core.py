import os
import signal
import sys
import yaml
import warnings

# Append the POCS dir to the system path.
pocs_dir = os.getenv('POCS', os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(pocs_dir)

from .utils.logger import has_logger
from .utils.config import load_config
from .utils.database import PanMongo

from .state_machine import PanStateMachine
from .observatory import Observatory

@has_logger
class Panoptes(PanStateMachine):

    """ A Panoptes object is in charge of the entire unit.

    An instance of this object is responsible for total control
    of a PANOPTES unit. Has access to the observatory, state machine,
    a parameter server, and a messaging channel.

    Args:
        connect_on_startup: Controls whether unit should try to connect
            when object is created. Defaults to False
    """

    def __init__(self, *args, **kwargs):
        self.logger.info('*' * 80)
        self.logger.info('Initializing PANOPTES unit')
        
        # Initialize the state machine. See `PanStateMachine` for details.
        super().__init__(*args, **kwargs)

        self._check_environment()

        self.logger.info('Checking config')
        self.config = load_config()
        self._check_config()

        # Setup the param server
        self.logger.info('Setting up database connection')
        self.db = PanMongo()

        # Create our observatory, which does the bulk of the work
        self.logger.info('Setting up observatory')
        self.observatory = Observatory(config=self.config)

        if self.config.get('connect_on_startup', False):
            self.logger.info('Initializing mount')
            self.observatory.mount.initialize()

    def _check_environment(self):
        """ Checks to see if environment is set up correctly

        There are a number of environmental variables that are expected
        to be set in order for PANOPTES to work correctly. This method just
        sanity checks our environment.

            POCS    Base directory for PANOPTES
        """
        if os.getenv('POCS') is None:
            warnings.warn('Please make sure $POCS environment variable is set')
            self.shutdown()
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


if __name__ == '__main__':
    pan = Panoptes()
