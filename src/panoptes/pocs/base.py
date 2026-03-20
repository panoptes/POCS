"""Common base utilities for POCS classes.

Provides PanBase, which centralizes access to configuration, logging, and the
shared lightweight database handle used throughout the project.
"""

import os
from typing import Any

from requests.exceptions import ConnectionError

from panoptes.utils.config import client
from panoptes.utils.telemetry import TelemetryClient

from panoptes.pocs import __version__, hardware
from panoptes.pocs.utils.logger import get_logger

# Global telemetry client.
PAN_TELEMETRY_OBJ = None

# Cache for config values that are `remember`ed.
PAN_CONFIG_CACHE = {}


class PanBase:
    """Base class for other classes within the PANOPTES ecosystem

    Defines common properties for each class (e.g. logger, config).
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

        global PAN_TELEMETRY_OBJ
        if PAN_TELEMETRY_OBJ is None:
            telemetry_host = kwargs.get(
                "telemetry_host",
                os.getenv("PANOPTES_TELEMETRY_HOST", self.get_config("telemetry.host", default="localhost")),
            )
            telemetry_port = kwargs.get(
                "telemetry_port",
                os.getenv("PANOPTES_TELEMETRY_PORT", self.get_config("telemetry.port", default=6562)),
            )
            PAN_TELEMETRY_OBJ = TelemetryClient(host=telemetry_host, port=telemetry_port)

        self.telemetry = PAN_TELEMETRY_OBJ

    def record_telemetry(self, model, **kwargs):
        """Record a telemetry event.

        This method centralizes data recording using the telemetry server.

        Args:
            model (pydantic.BaseModel | dict): The telemetry model or data to record.
            **kwargs: Passed to `post_event`.
        """
        # Get event_type from kwargs if provided, then pop it.
        event_type = kwargs.pop("event_type", "unknown")

        if hasattr(model, "model_dump"):
            data = model.model_dump(mode="json")
            # Prefer model's type if available.
            event_type = getattr(model, "type", event_type)
        else:
            data = model

        # Record to telemetry server.
        try:
            return self.telemetry.post_event(event_type, data, **kwargs)
        except Exception as e:
            self.logger.warning(f"Could not record to telemetry server: {e!r}")

    def _get_telemetry_timestamp(self, record):
        """Helper to extract a timestamp from a telemetry record.

        Prefer 'timestamp' in the data payload (useful for mocked time in tests),
        falling back to the 'ts' field in the record envelope.

        Args:
            record (dict): The telemetry record from `current_event`.

        Returns:
            datetime.datetime | None: The extracted timestamp or None if not found.
        """
        if not record:
            return None

        data = record.get("data", {})
        ts = data.get("timestamp") or record.get("ts")

        if ts is None:
            return None

        from datetime import datetime

        if isinstance(ts, str):
            try:
                return datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except Exception:
                return None
        elif isinstance(ts, datetime):
            return ts

        return None

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
