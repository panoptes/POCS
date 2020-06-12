from requests.exceptions import ConnectionError

from panoptes.pocs import __version__
from panoptes.utils.database import PanDB
from panoptes.utils.config import client
from panoptes.pocs.utils.logger import get_logger


class PanBase(object):
    """ Base class for other classes within the PANOPTES ecosystem

    Defines common properties for each class (e.g. logger, config, db).
    """

    def __init__(self, config_port='6563', *args, **kwargs):
        self.__version__ = __version__

        self._config_port = config_port

        self.logger = get_logger()

        simulators = self.get_config('simulator', default=[])
        if simulators:
            self.logger.warning(f'Using simulators: {simulators}')

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
            *args: Passed to get_config
            **kwargs: Passed to get_config
        """
        config_value = None
        try:
            config_value = client.get_config(port=self._config_port, *args, **kwargs)
        except ConnectionError as e:  # pragma: no cover
            self.logger.critical(f'Cannot connect to config_server from {self.__class__}: {e!r}')

        return config_value

    def set_config(self, key, new_value, *args, **kwargs):
        """Thin-wrapper around client based set_config that sets default port.

        See `panoptes.utils.config.client.set_config` for more information.

        Args:
            key (str): The key name to use, can be namespaced with dots.
            new_value (any): The value to store.
            *args: Passed to set_config
            **kwargs: Passed to set_config
        """
        config_value = None
        try:
            self.logger.debug(f'Setting config {key=} {new_value=}')
            config_value = client.set_config(key, new_value, port=self._config_port, *args, **kwargs)
            self.logger.debug(f'Config set {key=} {new_value=}')
        except ConnectionError as e:  # pragma: no cover
            self.logger.critical(f'Cannot connect to config_server from {self.__class__}: {e!r}')

        return config_value
