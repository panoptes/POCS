"""Common base utilities for POCS classes.

Provides PanBase, which centralizes access to configuration, logging, and the
shared lightweight telemetry client handle used throughout the project.
"""

import warnings
from typing import Any

from loguru import logger as _bootstrap_logger

from panoptes.utils.config import store as config_store
from panoptes.utils.telemetry import TelemetryClient

from panoptes.pocs import __version__, hardware
from panoptes.pocs.utils.logger import get_logger

# Global telemetry client.
PAN_TELEMETRY_OBJ = None


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

        # Explicitly initialise the config store on first use so the resolved
        # config file path is logged before any config lookups are made.
        if not config_store._CONFIG:
            loaded = config_store.init_config()
            if loaded:
                _bootstrap_logger.info(
                    f"PANOPTES config store initialised from {config_store._CONFIG_FILE!r} "
                    f"({len(loaded)} top-level keys)."
                )
            else:
                _bootstrap_logger.debug(
                    "PANOPTES config store: no config file found. "
                    "Set $PANOPTES_CONFIG_FILE or create ~/.panoptes/config.yaml. "
                    "Run `pocs config setup` to create one."
                )

        log_dir = self.get_config("directories.base", default=".") + "/../logs"
        cloud_logging_level = kwargs.get(
            "cloud_logging_level",
            self.get_config("panoptes_network.cloud_logging_level", default=None),
        )
        self.logger = get_logger(
            log_dir=kwargs.get("log_dir", log_dir), cloud_logging_level=cloud_logging_level
        )

        global PAN_TELEMETRY_OBJ
        if "db" in kwargs:
            PAN_TELEMETRY_OBJ = kwargs.pop("db")
        elif PAN_TELEMETRY_OBJ is None:
            telemetry_host = kwargs.get(
                "telemetry_host",
                os.getenv("PANOPTES_TELEMETRY_HOST", self.get_config("telemetry.host", default="localhost")),
            )
            telemetry_port = int(
                kwargs.get(
                    "telemetry_port",
                    os.getenv("PANOPTES_TELEMETRY_PORT", self.get_config("telemetry.port", default=6562)),
                )
            )
            PAN_TELEMETRY_OBJ = TelemetryClient(host=telemetry_host, port=telemetry_port)

        self.db = PAN_TELEMETRY_OBJ

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
