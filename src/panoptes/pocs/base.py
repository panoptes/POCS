"""Common base utilities for POCS classes.

Provides PanBase, which centralizes access to configuration, logging, and the
shared lightweight database handle used throughout the project.
"""

import os
from typing import Any

from requests.exceptions import ConnectionError

from panoptes.utils.config import client
from panoptes.utils.database import PanDB
from panoptes.utils.telemetry import TelemetryClient

from panoptes.pocs import __version__, hardware
from panoptes.pocs.utils.logger import get_logger

# Global database.
PAN_DB_OBJ = None

# Global telemetry client.
PAN_TELEMETRY_OBJ = None

# Cache for config values that are `remember`ed.
PAN_CONFIG_CACHE = {}


class PanBase:
    """Base class for other classes within the PANOPTES ecosystem

    Defines common properties for each class (e.g. logger, config, db).
    """

    def __init__(self, config_host=None, config_port=None, *args, **kwargs):
        self.__version__ = __version__

        self._config_host = config_host or os.getenv("PANOPTES_CONFIG_HOST", "localhost")
        self._config_port = config_port or os.getenv("PANOPTES_CONFIG_PORT", 6563)

        log_dir = self.get_config("directories.base", default=".") + "/../logs"
        cloud_logging_level = kwargs.get(
            "cloud_logging_level",
            self.get_config("panoptes_network.cloud_logging_level", default=None),
        )
        self.logger = get_logger(
            log_dir=kwargs.get("log_dir", log_dir), cloud_logging_level=cloud_logging_level
        )

        global PAN_DB_OBJ
        if PAN_DB_OBJ is None:
            # If the user requests a db_type then update runtime config.
            db_name = kwargs.get("db_name", self.get_config("db.name", default="panoptes"))
            db_folder = kwargs.get("db_folder", self.get_config("db.folder", default="json_store"))
            db_type = kwargs.get("db_type", self.get_config("db.type", default="file"))

            PAN_DB_OBJ = PanDB(db_name=db_name, storage_dir=db_folder, db_type=db_type)

        self.db = PAN_DB_OBJ

        global PAN_TELEMETRY_OBJ
        if PAN_TELEMETRY_OBJ is None:
            telemetry_host = kwargs.get("telemetry_host", self.get_config("telemetry.host", default="localhost"))
            telemetry_port = kwargs.get("telemetry_port", self.get_config("telemetry.port", default=6565))
            PAN_TELEMETRY_OBJ = TelemetryClient(host=telemetry_host, port=telemetry_port)

        self.telemetry = PAN_TELEMETRY_OBJ

    def record_telemetry(self, model, store_permanently=False, **kwargs):
        """Record a telemetry event.

        This method centralizes data recording, handling both the legacy database
        (insert_current) and the new telemetry server.

        Args:
            model (pydantic.BaseModel | dict): The telemetry model or data to record.
            store_permanently (bool): If the data should be stored permanently in the legacy DB.
            **kwargs: Passed to `post_event` and `insert_current`.
        """
        if hasattr(model, "model_dump"):
            data = model.model_dump()
            event_type = getattr(model, "type", "unknown")
        else:
            data = model
            event_type = kwargs.pop("event_type", "unknown")

        # Record to legacy database for backward compatibility.
        try:
            self.db.insert_current(event_type, data, store_permanently=store_permanently)
        except Exception as e:
            self.logger.warning(f"Could not record to legacy database: {e!r}")

        # Record to telemetry server.
        try:
            return self.telemetry.post_event(event_type, data, **kwargs)
        except Exception as e:
            self.logger.warning(f"Could not record to telemetry server: {e!r}")

    def get_config(
        self, key: str, default: Any | None = None, remember: bool = False, *args, **kwargs
    ) -> Any:
        """Thin-wrapper around client based get_config that sets default port.

        See `panoptes.utils.config.client.get_config` for more information.

        Args:
            key (str): The key name to use, can be namespaced with dots.
            default (any): The default value to return if the key is not found.
            remember (bool): If True, cache the result for future calls.
            *args: Passed to get_config
            **kwargs: Passed to get_config

        Returns:
            Any: The retrieved configuration value, or the provided default if not found
                or if the config server is unavailable.
        """
        # Try to use the cache if we have it.
        if key in PAN_CONFIG_CACHE:
            self.logger.debug(f"Using cached config key={key!r} value={PAN_CONFIG_CACHE[key]!r}")
            return PAN_CONFIG_CACHE[key]

        config_value = None
        try:
            config_value = client.get_config(
                key=key,
                default=default,
                host=self._config_host,
                port=self._config_port,
                verbose=False,
                *args,
                **kwargs,
            )
        except ConnectionError as e:  # pragma: no cover
            self.logger.warning(f"Cannot connect to config_server from {self.__class__}: {e!r}")
            return config_value

        # Cache the value if requested.
        if remember:
            PAN_CONFIG_CACHE[key] = config_value
            self.logger.debug(f"Caching config key={key!r} value={config_value!r}")

        return config_value

    def set_config(self, key, new_value, *args, **kwargs):
        """Thin-wrapper around client based set_config that sets default port.

        See `panoptes.utils.config.client.set_config` for more information.

        Args:
            key (str): The key name to use, can be namespaced with dots.
            new_value (any): The value to store.
            *args: Passed to set_config
            **kwargs: Passed to set_config

        Returns:
            Any | None: The value returned by the config client after setting, or None
                if the config server is unavailable.
        """
        config_value = None

        if key == "simulator" and new_value == "all":
            # Don't use hardware.get_simulator_names because it checks config.
            new_value = [h.name for h in hardware.HardwareName]

        try:
            self.logger.trace(f"Setting config key={key!r} new_value={new_value!r}")
            config_value = client.set_config(
                key, new_value, host=self._config_host, port=self._config_port, *args, **kwargs
            )
            self.logger.trace(f"Config set config_value={config_value!r}")
        except ConnectionError as e:  # pragma: no cover
            self.logger.critical(f"Cannot connect to config_server from {self.__class__}: {e!r}")

        return config_value

    def clear_config_cache(self):
        """Clear the config cache."""
        global PAN_CONFIG_CACHE
        PAN_CONFIG_CACHE = {}
        self.logger.debug("Cleared config cache")
