import random

from pocs.dome import AbstractDome


class Dome(AbstractDome):
    """Simulator for a Dome controller."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._state = 'Disconnected'

    @property
    def is_open(self):
        return self._state == 'Open'

    @property
    def is_closed(self):
        return self._state == 'Closed'

    @property
    def status(self):
        # Deliberately not a keyword to emphasize that this is for presentation, not logic.
        return 'Dome is {}'.format(self._state)

    def connect(self):
        if not self.is_connected:
            self._is_connected = True
            # Pick a random initial state.
            self._state = random.choice(['Open', 'Closed', 'Unknown'])
        return self.is_connected

    def disconnect(self):
        self._is_connected = False
        return True

    def open(self):
        self._state = 'Open'
        return self.is_open

    def close(self):
        self._state = 'Closed'
        return self.is_closed
