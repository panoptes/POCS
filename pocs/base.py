import sys

from pocs import __version__
from pocs.utils import config
from pocs.utils.database import PanMongo
from pocs.utils.logger import get_root_logger

# Global vars
_config = None
_logger = None


class PanBase(object):

    """ Base class for other classes within the Pan ecosystem

    Defines common properties for each class (e.g. logger, config)self.
    """

    def __init__(self, *args, **kwargs):
        # Load the default and local config files
        global _config
        if _config is None:
            ignore_local_config = kwargs.get('ignore_local_config', False)
            _config = config.load_config(ignore_local=ignore_local_config)

        # Update with run-time config
        if 'config' in kwargs:
            _config.update(kwargs['config'])

        self.__version__ = __version__
        self._check_config(_config)
        self.config = _config

        global _logger
        if _logger is None:
            _logger = get_root_logger()
            _logger.info('{:*^80}'.format(' Starting POCS '))

        self.logger = kwargs.get('logger', _logger)

        if 'simulator' in kwargs:
            if 'all' in kwargs['simulator']:
                self.config['simulator'] = ['camera', 'mount', 'weather', 'night']
            else:
                self.config['simulator'] = kwargs['simulator']

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
