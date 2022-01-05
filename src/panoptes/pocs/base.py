import os

from panoptes.pocs import __version__
from panoptes.pocs import hardware
from panoptes.pocs.utils.logger import get_logger
from panoptes.utils.config import client
from panoptes.utils.database import PanDB
from requests.exceptions import ConnectionError

# Global database.
PAN_DB_OBJ = None


class PanBase(object):
    """ Base class for other classes within the PANOPTES ecosystem

    Defines common properties for each class (e.g. logger, config, db).
    """

    def __init__(self, config_host=None, config_port=None, *args, **kwargs):
        self.__version__ = __version__

        self._config_host = config_host or os.getenv('PANOPTES_CONFIG_HOST', 'localhost')
        self._config_port = config_port or os.getenv('PANOPTES_CONFIG_PORT', 6563)

        self.logger = get_logger(log_dir=kwargs.get('log_dir', 'logs'))

        global PAN_DB_OBJ
        if PAN_DB_OBJ is None:
            # If the user requests a db_type then update runtime config
            db_type = kwargs.get('db_type', self.get_config('db.type', default='file'))
            db_name = kwargs.get('db_name', self.get_config('db.name', default='panoptes'))
            db_folder = kwargs.get('db_folder', self.get_config('db.folder', default='json_store'))

            PAN_DB_OBJ = PanDB(db_type=db_type, db_name=db_name, storage_dir=db_folder)

        self.db = PAN_DB_OBJ

    def get_config(self, *args, **kwargs):
        """Thin-wrapper around client based get_config that sets default port.

        See `panoptes.utils.config.client.get_config` for more information.

        Args:
            *args: Passed to get_config
            **kwargs: Passed to get_config
        """
        config_value = None
        try:
            config_value = client.get_config(host=self._config_host,
                                             port=self._config_port,
                                             verbose=False,
                                             *args, **kwargs)
        except ConnectionError as e:  # pragma: no cover
            self.logger.warning(f'Cannot connect to config_server from {self.__class__}: {e!r}')

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

        if key == 'simulator' and new_value == 'all':
            # Don't use hardware.get_simulator_names because it checks config.
            new_value = [h.name for h in hardware.HardwareName]

        try:
            self.logger.trace(f'Setting config key={key!r} new_value={new_value!r}')
            config_value = client.set_config(key, new_value,
                                             host=self._config_host,
                                             port=self._config_port,
                                             *args, **kwargs)
            self.logger.trace(f'Config set config_value={config_value!r}')
        except ConnectionError as e:  # pragma: no cover
            self.logger.critical(f'Cannot connect to config_server from {self.__class__}: {e!r}')

        return config_value
