"""Common base utilities for POCS classes.

Provides PanBase, which centralizes access to configuration, logging, and the
shared lightweight database handle used throughout the project.
"""

import warnings
from typing import Any

from panoptes.utils.config import store as config_store
from panoptes.utils.database import PanDB

from panoptes.pocs import __version__, hardware
from panoptes.pocs.utils.logger import get_logger

# Global database.
PAN_DB_OBJ = None


class PanBase:
    """Base class for other classes within the PANOPTES ecosystem.

    Defines common properties for each class (e.g. logger, config, db).
    """

    def __init__(self, config_host=None, config_port=None, *args, **kwargs):
        self.__version__ = __version__

        if config_host is not None or config_port is not None:
            warnings.warn(
                "config_host and config_port are deprecated and have no effect. "
                "Config is now loaded directly from the PANOPTES config file.",
                DeprecationWarning,
                stacklevel=2,
            )

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
            db_name = kwargs.get("db_name", self.get_config("db.name", default="panoptes"))
            db_folder = kwargs.get("db_folder", self.get_config("db.folder", default="json_store"))
            db_type = kwargs.get("db_type", self.get_config("db.type", default="file"))
            PAN_DB_OBJ = PanDB(db_name=db_name, storage_dir=db_folder, db_type=db_type)

        self.db = PAN_DB_OBJ

    def get_config(
        self, key: str | None = None, default: Any | None = None, remember: bool = False, *args, **kwargs
    ) -> Any:
        """Get a config value by dotted key name.

        Args:
            key: Dotted key e.g. ``"location.latitude"``. ``None`` returns the full config dict.
            default: Value to return if the key is not found.
            remember: Accepted for backward compatibility but has no effect.
            *args: Ignored.
            **kwargs: Ignored.

        Returns:
            The config value, or *default* if not found.
        """
        del remember, args, kwargs
        return config_store.get_config(key=key, default=default)

    def set_config(self, key: str, new_value: Any, persist: bool = True, *args, **kwargs) -> Any:
        """Set a config value by dotted key name.

        Args:
            key: Dotted key e.g. ``"location.latitude"``.
            new_value: The value to store.
            persist: Write the updated config back to disk. Defaults to ``True``.
            *args: Ignored.
            **kwargs: Ignored.

        Returns:
            The new value.
        """
        del args, kwargs
        if key == "simulator" and new_value == "all":
            new_value = [h.name for h in hardware.HardwareName]

        self.logger.trace(f"Setting config key={key!r} new_value={new_value!r}")
        return config_store.set_config(key, new_value, persist=persist)

    def clear_config_cache(self):
        """Reload config from the source file, discarding any in-memory changes."""
        config_store.reload_config()
        self.logger.debug("Config reloaded from file")
