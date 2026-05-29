"""Action handlers for the POCS TUI control interface.

All side effects go through this module. Every attempt and outcome is
written to CmdLog so operators have a full audit trail.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from panoptes.pocs.tui.bridge import Bridge
    from panoptes.pocs.tui.cmdlog import CmdLog
    from panoptes.pocs.tui.model import POCSModel


def _log(cmdlog: Any, level: str, msg: str) -> None:
    if cmdlog is not None and hasattr(cmdlog, "push"):
        cmdlog.push(level, msg)


def action_initialize(bridge: Bridge, cmdlog: CmdLog, model: POCSModel | None = None) -> None:
    """Request background POCS initialization."""
    _log(cmdlog, "INFO", "Initialize requested")
    bridge.initialize()


def action_start_run(bridge: Bridge, cmdlog: CmdLog, model: POCSModel | None = None) -> None:
    """Request the nightly run loop."""
    _log(cmdlog, "INFO", "Start nightly run requested")
    bridge.start_run()


def action_stop_run(bridge: Bridge, cmdlog: CmdLog, model: POCSModel | None = None) -> None:
    """Present confirmation modal before stopping the run."""
    if model is not None:
        model.modal.active = True
        model.modal.prompt = "Stop the current observing run?"
        model.modal.choices = ["Confirm", "Cancel"]
        model.modal.selected = 1
        model.modal.callback = "action_stop_run_confirmed"
    else:
        _log(cmdlog, "WARN", "Stop run requested (no confirmation)")
        bridge.stop_run()


def action_stop_run_confirmed(bridge: Bridge, cmdlog: CmdLog, model: POCSModel | None = None) -> None:
    """Stop the active run after confirmation."""
    _log(cmdlog, "WARN", "Run stopped by operator")
    bridge.stop_run()


def action_park(bridge: Bridge, cmdlog: CmdLog, model: POCSModel | None = None) -> None:
    """Request the mount to park."""
    _log(cmdlog, "INFO", "Park requested")
    bridge.park()


def action_power_down(bridge: Bridge, cmdlog: CmdLog, model: POCSModel | None = None) -> None:
    """Present confirmation modal before powering down."""
    if model is not None:
        model.modal.active = True
        model.modal.prompt = "Shut down POCS and park the mount?"
        model.modal.choices = ["Confirm", "Cancel"]
        model.modal.selected = 1
        model.modal.callback = "action_power_down_confirmed"
    else:
        bridge.power_down()


def action_power_down_confirmed(bridge: Bridge, cmdlog: CmdLog, model: POCSModel | None = None) -> None:
    """Run full power-down after confirmation."""
    _log(cmdlog, "WARN", "POCS power-down initiated by operator")
    bridge.power_down()


def action_quit(bridge: Bridge, cmdlog: CmdLog, model: POCSModel | None = None) -> None:
    """Present confirmation modal before quitting the TUI."""
    if model is not None:
        model.modal.active = True
        model.modal.prompt = "Quit the TUI? (POCS will keep running)"
        model.modal.choices = ["Quit", "Cancel"]
        model.modal.selected = 1
        model.modal.callback = "action_quit_confirmed"


def action_quit_confirmed(bridge: Bridge, cmdlog: CmdLog, model: POCSModel | None = None) -> None:
    """Set the sentinel state used by the main loop to exit."""
    del bridge, cmdlog
    if model is not None:
        model.system.state = "__quit__"


def action_abort_exposure(bridge: Bridge, cmdlog: CmdLog, model: POCSModel | None = None) -> None:
    """Abort all active exposures."""
    _log(cmdlog, "WARN", "Abort exposure requested")
    bridge.abort_exposure()


def action_snapshot(bridge: Bridge, cmdlog: CmdLog, model: POCSModel | None = None) -> None:
    """Record a manual snapshot request."""
    del bridge, model
    _log(cmdlog, "INFO", "Manual snapshot requested")


def action_set_config(
    bridge: Bridge,
    cmdlog: CmdLog,
    model: POCSModel | None = None,
    *,
    key: str,
    value: Any,
) -> None:
    """Update a config key via the bridge."""
    del model
    ok = bridge.set_config(key, value)
    if ok:
        _log(cmdlog, "INFO", f"Config updated: {key} = {value!r}")
    else:
        _log(cmdlog, "ERROR", f"Config update failed: {key}")


def action_reload_config(bridge: Bridge, cmdlog: CmdLog, model: POCSModel | None = None) -> None:
    """Log a config reload request."""
    del bridge, model
    _log(cmdlog, "INFO", "Config reload requested (restart required for hardware changes)")


def action_not_implemented(
    bridge: Bridge,
    cmdlog: CmdLog,
    model: POCSModel | None = None,
    *,
    label: str,
) -> None:
    """Log selection of a placeholder action."""
    del bridge, model
    _log(cmdlog, "INFO", f"{label} is not implemented yet")


_ACTION_MAP: dict[str, Any] = {
    "action_initialize": action_initialize,
    "action_start_run": action_start_run,
    "action_stop_run": action_stop_run,
    "action_stop_run_confirmed": action_stop_run_confirmed,
    "action_park": action_park,
    "action_power_down": action_power_down,
    "action_power_down_confirmed": action_power_down_confirmed,
    "action_quit": action_quit,
    "action_quit_confirmed": action_quit_confirmed,
    "action_abort_exposure": action_abort_exposure,
    "action_snapshot": action_snapshot,
    "action_reload_config": action_reload_config,
}


def dispatch(
    action_name: str,
    bridge: Bridge,
    cmdlog: CmdLog,
    model: POCSModel | None = None,
    **kwargs: Any,
) -> None:
    """Look up and call an action handler by name.

    Args:
        action_name: Action function name to dispatch.
        bridge: Bridge used for side effects.
        cmdlog: Command log sink.
        model: Optional UI model for modal interactions.
        **kwargs: Extra action-specific keyword arguments.
    """
    handler = _ACTION_MAP.get(action_name)
    if handler is not None:
        handler(bridge, cmdlog, model, **kwargs)
    elif action_name == "action_polar_align":
        action_not_implemented(bridge, cmdlog, model, label="Polar alignment")
    elif action_name == "action_focus_run":
        action_not_implemented(bridge, cmdlog, model, label="Focus run")
    elif action_name == "action_take_darks":
        action_not_implemented(bridge, cmdlog, model, label="Take dark frames")
