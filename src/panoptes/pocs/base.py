from requests.exceptions import ConnectionError

from panoptes.pocs import __version__
from panoptes.utils.database import PanDB
from panoptes.utils.config import client
from panoptes.pocs.utils.logging import get_logger


class PanBase(object):
    """ Base class for other classes within the PANOPTES ecosystem

    Defines common properties for each class (e.g. logger, db).
    """

    def __init__(self, config_port='6563', *args, **kwargs):
        self.__version__ = __version__

        self._config_port = config_port

        self.logger = get_logger()

        simulators = self.get_config('simulator', default=[])
        if simulators:
            self.logger.warning(f'Using simulators: {simulators}')

        # Check to make sure config has some items we need
        self._check_config()

        # Get passed DB or set up new connection
        _db = kwargs.get('db', None)
        if _db is None:
            # If the user requests a db_type then update runtime config
            db_type = kwargs.get('db_type', self.get_config('db.type', default='file'))
            db_name = kwargs.get('db_name', self.get_config('db.name', default='panoptes'))

            _db = PanDB(db_type=db_type, db_name=db_name)

        self.db = _db

    def get_config(self, *args, **kwargs):
        """Thin-wrapper around client based get_config that sets default port.

        See `panoptes.utils.config.client.get_config` for more information.

        Args:
            *args: Passed to get_client
            **kwargs: Passed to get_client
        """
        config_value = None
        try:
            config_value = client.get_config(port=self._config_port, *args, **kwargs)
        except ConnectionError as e:  # pragma: no cover
            self.logger.critical(f'Cannot connect to config_server from {self.__class__}: {e!r}')

        return config_value

    def _check_config(self):
        """ Checks the config file for mandatory items """

        items_to_check = [
            'directories',
            'mount',
            'state_machine'
        ]

        for item in items_to_check:
            config_item = self.get_config(item, default={})
            if config_item is None or len(config_item) == 0:
                self.logger.error(f"'{item}' must be specified in config, exiting")
