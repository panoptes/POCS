import sys

from pocs import hardware
from pocs import __version__
from pocs.utils import config
from pocs.utils.database import PanDB
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

        # Get passed DB or set up new connection
        _db = kwargs.get('db', None)
        if _db is None:
            # If the user requests a db_type then update runtime config
            db_type = kwargs.get('db_type', None)
            db_name = kwargs.get('db_name', None)

            if db_type is not None:
                self.config['db']['type'] = db_type
            if db_name is not None:
                self.config['db']['name'] = db_name

            db_type = self.config['db']['type']
            db_name = self.config['db']['name']

            _db = PanDB(db_type=db_type, db_name=db_name, logger=self.logger)

        self.db = _db

    def _check_config(self, temp_config):
        """ Checks the config file for mandatory items """
        items_to_check = [
            'directories',
            'mount',
            'state_machine'
        ]

        for item in items_to_check:
            config_item = temp_config.get(item, None)
            # Warn if not found.
            if config_item is None:
                self.logger.critical(f'Problem looking up {item} in _check_config')
            # Error if not found or empty.
            if config_item is None or len(config_item) == 0:
                sys.exit(f'{item} must be specified in config, exiting')

    def __getstate__(self):  # pragma: no cover
        d = dict(self.__dict__)

        if 'logger' in d:
            del d['logger']

        if 'db' in d:
            del d['db']

        return d
