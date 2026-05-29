"""Action handlers for keyboard-driven POCS TUI controls."""

from __future__ import annotations

from typing import Any


def cmdlog_push(cmdlog: Any, level: str, msg: str) -> None:
    """Push a log entry if a compatible command log object is provided.

    Args:
        cmdlog: Object exposing ``push(level, msg)``.
        level: Severity label such as ``INFO`` or ``ERROR``.
        msg: Human-readable action message.
    """
    if cmdlog is not None and hasattr(cmdlog, "push"):
        cmdlog.push(level, msg)


def action_park(pocs: Any, cmdlog: Any) -> None:
    """Request parking the mount through the TUI control plane.

    Args:
        pocs: Running POCS object the action will target.
        cmdlog: Command log sink used for operator-visible auditing.

    Returns:
        None
    """
    cmdlog_push(cmdlog, "INFO", "action_park requested")
    # TODO: Call the relevant POCS park operation and capture success/failure in cmdlog.
    return None


def action_abort_exposure(pocs: Any, cmdlog: Any) -> None:
    """Request aborting active camera exposure(s) from keyboard input.

    Args:
        pocs: Running POCS object the action will target.
        cmdlog: Command log sink used for operator-visible auditing.

    Returns:
        None
    """
    cmdlog_push(cmdlog, "WARN", "action_abort_exposure requested")
    # TODO: Stop active exposures safely and log the outcome.
    return None


def action_snapshot(pocs: Any, cmdlog: Any) -> None:
    """Request a one-shot data refresh after an operator command.

    Args:
        pocs: Running POCS object the action will target.
        cmdlog: Command log sink used for operator-visible auditing.

    Returns:
        None
    """
    cmdlog_push(cmdlog, "INFO", "action_snapshot requested")
    # TODO: Trigger immediate scanner refresh and record command result.
    return None
