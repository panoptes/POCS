"""Thread-safe command log for TUI actions."""

from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock


@dataclass(slots=True)
class LogEntry:
    """A single command-log entry."""

    ts: datetime
    level: str
    msg: str


class CmdLog:
    """Ring buffer of recent command actions and outcomes."""

    def __init__(self) -> None:
        self._entries: deque[LogEntry] = deque(maxlen=64)
        self._lock = Lock()

    def push(self, level: str, msg: str) -> LogEntry:
        """Append a new command entry and return it."""
        entry = LogEntry(ts=datetime.now(UTC), level=level, msg=msg)
        with self._lock:
            self._entries.append(entry)
        return entry

    def tail(self, n: int) -> list[LogEntry]:
        """Return up to the most recent ``n`` entries."""
        if n <= 0:
            return []
        with self._lock:
            return list(self._entries)[-n:]
