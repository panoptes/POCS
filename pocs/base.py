import sys

from pocs import __version__
from panoptes.utils.database import PanDB
from panoptes.utils.config import client
from panoptes.utils.logger import get_root_logger


class PanBase(object):

    """ Base class for other classes within the PANOPTES ecosystem

    Defines common properties for each class (e.g. logger, db).
    """

    def __init__(self, config_port='6563', *args, **kwargs):
        self.__version__ = __version__

        self._config_port = config_port

        # Check to make sure config has some items we need
        self._check_config()

        self.logger = kwargs.get('logger')
        if not self.logger:
            self.logger = get_root_logger()

        # Get passed DB or set up new connection
        _db = kwargs.get('db', None)
        if _db is None:
            # If the user requests a db_type then update runtime config
            db_type = kwargs.get('db_type', None)
            db_name = kwargs.get('db_name', None)

            db_type = self.get_config('db.type')
            db_name = self.get_config('db.name')

            _db = PanDB(db_type=db_type, db_name=db_name, logger=self.logger)

        self.db = _db

    def get_config(self, *args, **kwargs):
        """Thin-wrapper around client based get_config that sets default port.

        See `panoptes.utils.config.client.get_config` for more information.

        Args:
            *args: Passed to get_client
            **kwargs: Passed to get_client
        """
        return client.get_config(port=self._config_port, *args, **kwargs)

    def _check_config(self):
        """ Checks the config file for mandatory items """

        items_to_check = [
            'directories',
            'mount',
            'state_machine'
        ]

        for item in items_to_check:
            if len(self.get_config(item, default={})) == 0:
                sys.exit(f'{item} must be specified in config, exiting')
