"""Backward-compatible re-export from panoptes.utils.config.store.

The config store has been moved upstream to panoptes-utils. This module is
retained so existing imports of the form::

    from panoptes.pocs.config.store import get_config, set_config

continue to work without modification.  New code should import from
:mod:`panoptes.utils.config.store` directly.
"""

from panoptes.utils.config.store import (  # noqa: F401
    _CONFIG,
    _CONFIG_FILE,
    _get_nested,
    _set_nested,
    get_config,
    init_config,
    reload_config,
    set_config,
)

__all__ = [
    "_CONFIG",
    "_CONFIG_FILE",
    "_get_nested",
    "_set_nested",
    "get_config",
    "init_config",
    "reload_config",
    "set_config",
]
