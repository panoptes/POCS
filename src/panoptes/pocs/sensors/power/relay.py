from abc import ABC, abstractmethod

from panoptes.utils.time import CountdownTimer
from ...utils.logger import get_logger

logger = get_logger()


class Relay(ABC):
    """Base class for an individual power relay."""

    def __init__(self, name, pin_number):
        """

        Args:
            name (str): The name associated with this relay.
            pin_number (int): The GPIO pin that will be toggled.
        """
        self.name = name
        self.pin_number = pin_number

        logger.success(f'Created {self}')

    @property
    def state(self):
        """The current state of the relay, either 'on' or 'off'."""
        return 'on' if self.is_on else 'off'

    @property
    @abstractmethod
    def is_on(self):
        """Check if relay is turned on."""
        return NotImplemented

    @property
    def is_off(self):
        """Check if relay is turned off."""
        return not self.is_on

    @abstractmethod
    def turn_on(self):
        """Turns the relay on."""
        return NotImplemented

    @abstractmethod
    def turn_off(self):
        """Turns the relay off."""
        return NotImplemented

    def toggle(self):
        """Toggles the relay, switching the current state."""
        if self.is_on:
            self.turn_off()
        else:
            self.turn_on()

    def power_cycle(self, delay=None):
        """Turns relay off, waits for a short delay, then turns relay on.

        Note that the relay will turn on even if it was off to begin with.

        Args:
            delay (scalar or None): The amount of time to wait before turning
                toggling to the `on` state.
        """
        logger.info(f'Power cycling {self}')

        self.turn_off()
        timer = CountdownTimer(delay)
        timer.sleep()
        self.turn_on()

        logger.success(f'Successful power cycle for {self}')

    def __str__(self):
        return f'{self.name} relay ({self.pin_number=})'
