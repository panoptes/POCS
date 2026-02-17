"""Simple dome simulator used by tests and demos.

Implements the AbstractDome interface with in-memory state transitions for
open/close/connect, returning canned status values.
"""

import random

from panoptes.pocs.dome import AbstractDome


class Dome(AbstractDome):
    """Simulator for a Dome controller."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._state = "disconnected"

    @property
    def is_open(self):
        """Whether the simulated dome slit is open.

        Returns:
            bool: True if the simulated state is 'open'.
        """
        return self._state == "open"

    @property
    def is_closed(self):
        """Whether the simulated dome slit is closed.

        Returns:
            bool: True if the simulated state is 'closed'.
        """
        return self._state == "closed"

    @property
    def status(self):
        """Return a minimal status dictionary for the simulated dome.

        Returns:
            dict: Contains `connected` (bool) and `open` (str state) keys.
        """
        return dict(connected=self.is_connected, open=self._state)

    def connect(self):
        """Connect to the simulated dome controller.

        Returns:
            bool: True if the simulator reports connected after the call.
        """
        if not self.is_connected:
            self._is_connected = True
            # Pick a random initial state.
            self._state = random.choice(["open", "closed", "unknown"])
        return self.is_connected

    def disconnect(self):
        """Disconnect from the simulated dome controller.

        Returns:
            bool: Always True for the simulator.
        """
        self._is_connected = False
        return True

    def open(self):
        """Open the simulated dome slit.

        Returns:
            bool: True if the state is now 'open'.
        """
        self._state = "open"
        return self.is_open

    def close(self):
        """Close the simulated dome slit.

        Returns:
            bool: True if the state is now 'closed'.
        """
        self._state = "closed"
        return self.is_closed
