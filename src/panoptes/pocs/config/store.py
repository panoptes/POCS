"""Module-level in-memory config store for POCS.

Provides get_config() and set_config() as drop-in replacements for the
legacy HTTP config client. Config is loaded from a YAML file once
at startup and held in memory.
"""

import re
from pathlib import Path
from typing import Any

from loguru import logger

from panoptes.utils.config.helpers import deep_merge
from panoptes.utils.config.helpers import load_config as _load_config_file

_CONFIG: dict[str, Any] = {}
_CONFIG_FILE: Path | None = None


def _get_nested(d: dict[str, Any], key: str, default: Any = None) -> Any:
    """Navigate a nested dict using dotted-key notation."""
    if not key:
        return d

    current: Any = d
    for part in key.split("."):
        if not isinstance(current, dict):
            return default

        if match := re.fullmatch(r"([^\[\]]+)(\[(-?\d+)\])?", part):
            name = match.group(1)
            index = match.group(3)
        else:
            name = part
            index = None

        if name not in current:
            return default

        current = current[name]

        if index is not None:
            if not isinstance(current, list):
                return default
            try:
                current = current[int(index)]
            except (IndexError, ValueError):
                return default

    return current


def init_config(config_file: str | Path | None = None) -> dict[str, Any]:
    """Load config from a file and initialise the module-level store.

    Args:
        config_file: Path to a YAML config file. If None, uses the previously
            configured path or falls back to the default panoptes-utils resolution
            ($PANOPTES_CONFIG_FILE → ~/.panoptes/config.yaml).

    Returns:
        The loaded config dict.
    """
    global _CONFIG, _CONFIG_FILE
    if config_file is not None:
        _CONFIG_FILE = Path(config_file)
    _CONFIG = _load_config_file(_CONFIG_FILE, load_local=False)
    logger.debug(f"Config initialised from {_CONFIG_FILE!r}")
    return _CONFIG


def reload_config() -> dict[str, Any]:
    """Reload the config from the same file used by init_config.

    Returns:
        The refreshed config dict.
    """
    return init_config(_CONFIG_FILE)


def get_config(key: str | None = None, default: Any = None, **kwargs) -> Any:
    """Get a config value by dotted-key name.

    If the store has not been initialised yet, it is initialised automatically
    using the default panoptes-utils file resolution.

    Args:
        key: Dotted key e.g. ``"location.latitude"``. ``None`` returns the full config dict.
        default: Value to return if the key is not found.
        **kwargs: Accepted but ignored (backward-compatible with old HTTP client signature).

    Returns:
        The config value, or *default* if the key is not found.
    """
    del kwargs
    if not _CONFIG:
        init_config()
    if key is None:
        return _CONFIG
    value = _get_nested(_CONFIG, key, default)
    logger.trace(f"get_config {key!r} -> {value!r}")
    return value


def set_config(key: str, new_value: Any, **kwargs) -> Any:
    """Set a config value by dotted-key name.

    Updates the in-memory store only (does not write to disk). Call
    ``panoptes.utils.config.helpers.save_config`` to persist changes.

    Args:
        key: Dotted key e.g. ``"location.latitude"``.
        new_value: The value to store.
        **kwargs: Accepted but ignored (backward-compatible with old HTTP client signature).

    Returns:
        *new_value* as stored.
    """
    del kwargs
    global _CONFIG
    if not _CONFIG:
        init_config()
    nested: Any = new_value
    for part in reversed(key.split(".")):
        nested = {part: nested}
    _CONFIG = deep_merge(_CONFIG, nested)
    logger.trace(f"set_config {key!r} = {new_value!r}")
    return new_value
