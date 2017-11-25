import random

from . import PanFixedDome


class Dome(PanFixedDome):
    """Simulator for a Dome controller."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._state = 'Disconnected'

    @property
    def is_open(self):
        return self.state == 'Open'

    @property
    def is_closed(self):
        return self.state == 'Closed'

    @property
    def state(self):
        return self._state

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
