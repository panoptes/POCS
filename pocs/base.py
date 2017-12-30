import sys

from pocs import hardware
from pocs import __version__
from pocs.utils import config
from pocs.utils.database import PanMongo
from pocs.utils.logger import get_root_logger

# Global vars
_config = None


def reset_global_config():
    """Reset the global _config to None.

    Globals such as _config make tests non-hermetic. Enable conftest.py to clear _config
    in an explicit fashion.
    """
    global _config
    _config = None


class PanBase(object):

    """ Base class for other classes within the PANOPTES ecosystem

    Defines common properties for each class (e.g. logger, config).
    """

    def __init__(self, *args, **kwargs):
        # Load the default and local config files
        global _config
        if _config is None:
            ignore_local_config = kwargs.get('ignore_local_config', False)
            _config = config.load_config(ignore_local=ignore_local_config)

        self.__version__ = __version__

        # Update with run-time config
        if 'config' in kwargs:
            _config.update(kwargs['config'])

        self._check_config(_config)
        self.config = _config

        self.logger = kwargs.get('logger')
        if not self.logger:
            self.logger = get_root_logger()

        self.config['simulator'] = hardware.get_simulator_names(config=self.config, kwargs=kwargs)

        # Set up connection to database
        db = kwargs.get('db', self.config['db']['name'])
        _db = PanMongo(db=db)

        self.db = _db

    def _check_config(self, temp_config):
        """ Checks the config file for mandatory items """

        if 'directories' not in temp_config:
            sys.exit('directories must be specified in config')

        if 'mount' not in temp_config:
            sys.exit('Mount must be specified in config')

        if 'state_machine' not in temp_config:
            sys.exit('State Table must be specified in config')

    def __getstate__(self):  # pragma: no cover
        d = dict(self.__dict__)

        if 'logger' in d:
            del d['logger']

        if 'db' in d:
            del d['db']

        return d
