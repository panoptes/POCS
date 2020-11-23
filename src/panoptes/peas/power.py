from contextlib import suppress
import time
from enum import IntEnum
from collections import deque
from pymata4 import pymata4

from panoptes.pocs.base import PanBase


class PinState(IntEnum):
    """Represents a HIGH or LOW state for a digital output pin."""
    LOW = 0
    OFF = 0
    HIGH = 1
    ON = 1


class RelayPins(IntEnum):
    """The pins for the relays."""
    RELAY_0 = 17  # A3
    RELAY_1 = 3
    RELAY_2 = 4
    RELAY_3 = 7
    RELAY_4 = 8


class CurrentSensePins(IntEnum):
    """Analog pins on which the current can be read."""
    IS_0 = 0  # A0 - Sensing for RELAY_0 or RELAY_1
    IS_1 = 1  # A1 - Sensing for RELAY_2 or RELAY_3
    IS_2 = 2  # A2 - Sensing for RELAY_4


class CurrentSelectPins(IntEnum):
    """Pins for selecting current sensing channel of a PROFET."""
    DSEL_0 = 2  # LOW for RELAY_0, HIGH for RELAY_1
    DSEL_1 = 6  # LOW for RELAY_2, HIGH for RELAY_3


class CurrentEnablePins(IntEnum):
    """Pins for enabling the current sensing."""
    DEN_0 = 18  # A4 - Enable RELAY_0 and RELAY_1
    DEN_1 = 5  # Enable RELAY_2 and RELAY_3
    DEN_2 = 9  # Enable RELAY_4


class PowerBoard(PanBase):
    """Power distribution and monitoring.

    This represents a "trucker" board for PANOPTES, which is a combination of an
    Arduino Uno and an Infineon 24V relay shield.

    Pin names specified above correspond to Infineon terminology. See manual:
    https://bit.ly/2IGgWLQ.
    """

    def __init__(self,
                 name='Power Board',
                 arduino_instance_id=None,
                 relays=None,
                 *args, **kwargs):
        """Initialize the power board.

        The `relays` should be a dictionary with the relay name as key and a
        dict with `label` and `initial_state` entries::

            RELAY_0:
                label: mount
                initial_state: on

        Args:
            name (str): The user-friendly name for the power board.
            arduino_instance_id (int or None): If multiple arduinos are present
                on the system the specific board can be specified with this parameter.
                Requires setting the instance_id in the arduino sketch before upload.
                If None, pymata will attempt auto-discovery of the arduinos.
            relays (dict or None): The relay configuration. See notes for details.
                A default value of None will attempt to look up relays in the
                config-server.
        """
        super().__init__(*args, **kwargs)

        self.name = name

        # Lookup config for power board.
        self.config = self.get_config('environment.power')

        arduino_instance_id = arduino_instance_id or self.config.get('arduino_instance_id', 1)
        self.current_readings = dict()

        # Set up the PymataExpress board.
        self.logger.debug(f'Setting up Power board connection')
        self.board = pymata4.Pymata4(arduino_instance_id=arduino_instance_id)

        # Set initial pin modes.
        self.pin_states = dict()
        self.set_pin_modes()

        self.relays = dict()

        # Set relays.
        relays_config = relays or self.config.get('relays', dict())
        self.logger.debug(f'Setting initial relay states')
        for relay_name, relay_config in relays_config.items():
            relay_label = relay_config.get('label') or relay_name

            # Create relay object.
            self.logger.debug(f'Creating relay_label={relay_label} for {relay_config}')
            relay = Relay(self.board, RelayPins[relay_name].value, relay_name, **relay_config)

            # Add attribute for the board.
            setattr(self, relay_label, relay)

            # Add to relays list by name, label, and pin_number, which should all be different.
            self.relays[relay.name] = relay
            self.relays[relay.label] = relay
            self.relays[relay.pin_number] = relay

            self.logger.info(f'{relay_label} added to board: {relay}')

        self.logger.success(f'Power board initialized')
        self.logger.info(f'Relays: {self.relays!r}')

    def set_pin_modes(self, analog_callback=None, analog_differential=0):
        """Set the pin modes for the Arduino Uno + Infineon Uno 24V shield.

        An optional callback can be specified for the analog input pins. This
        callback should accept a single parameter that will be populated with a
        list containing: [pin, current reported value, pin_mode, timestamp]

        Args:
            analog_differential (int): Input values are only reported if the difference
                between the current value and the previous exceeds the differential.
                Default value is 5 (of 1023).
            analog_callback (callable): The callback for reading the analog input
                pins. See above for details. If no callback is specified the default
                `self.analog_callback` is used.
        """
        if analog_callback is None:
            analog_callback = self.analog_callback

        for pin in CurrentEnablePins:
            self.logger.info(f'Setting current enable pin={pin} as digital output with state=high')
            self.board.set_pin_mode_digital_output(pin.value)
            self.set_pin_state(pin.value, PinState.HIGH)

        for pin in RelayPins:
            self.logger.info(f'Setting relay pin={pin} as digital output')
            self.board.set_pin_mode_digital_output(pin.value)

        for pin in CurrentSelectPins:
            self.logger.info(f'Setting current select pin={pin} as digital output with state=low')
            self.board.set_pin_mode_digital_output(pin.value)
            self.set_pin_state(pin.value, PinState.LOW)

        for pin in CurrentSensePins:
            self.logger.debug(f'Setting current sense pin={pin} as analog input')
            self.board.set_pin_mode_analog_input(pin.value,
                                                 callback=analog_callback,
                                                 differential=analog_differential)

    def set_pin_state(self, pin_number, state):
        """Set the relay to the given state.

        Args:
            pin_number (int or Enum): The pin number of the relay to turn on.
            state (bool or PinState): A state that evaluates to True for "on" and False for "off".

        Returns:
            bool: True if pin state successfully set.
        """
        # Assume pin_number is an enum
        with suppress(AttributeError):
            pin_number = pin_number.value

        state = PinState(bool(state)).value
        self.logger.trace(f'Setting digital output pin={pin_number} to {state}')
        self.board.digital_write(pin_number, state)
        self.pin_states[pin_number] = state

    def get_pin_state(self, pin_number):
        """Get the digital pin state.

        Args:
            pin_number (int or str or Enum): The pin number or name of the relay
                to read state from.

        Returns:
            bool: True if pin is HIGH, False if LOW.
        """
        with suppress(AttributeError):
            pin_number = pin_number.value
        state, timestamp = self.board.digital_read(pin_number)
        self.logger.info(f'{pin_number} = {state} (at {timestamp})')

        return bool(state)

    def analog_callback(self, data):
        """Print analog values as they are read.

        A callback function to report data changes.
        This will print the pin number, its reported value
        the pin type (digital, analog, etc.) and
        the date and time when the change occurred

        Copied from: https://mryslab.github.io/pymata4/

        Args:
            data (list): A list containing: [pin, value, pin_mode, timestamp]
        """
        sense_pin = CurrentSensePins(data[1])
        sense_value = data[2]

        self.logger.trace(f'Callback: {data!r} {sense_pin}')

        relay_lookup = {
            CurrentSensePins.IS_0: (RelayPins.RELAY_0.name, RelayPins.RELAY_1.name),
            CurrentSensePins.IS_1: (RelayPins.RELAY_2.name, RelayPins.RELAY_3.name),
            CurrentSensePins.IS_2: (RelayPins.RELAY_4.name,),
        }

        select_pin_lookup = {
            CurrentSensePins.IS_0: CurrentSelectPins.DSEL_0.value,
            CurrentSensePins.IS_1: CurrentSelectPins.DSEL_1.value,
        }

        relay = None
        # Get relay  names for the channel.
        relay_names = relay_lookup[sense_pin]

        try:
            if sense_pin == CurrentSensePins.IS_2.value:
                with suppress(KeyError):
                    relay = self.relays[relay_names[0]]
            else:
                # See if channel is high or low.
                select_state = self.pin_states[select_pin_lookup[sense_pin]]

                # Get the relay based on which channel is selected.
                relay = self.relays[relay_names[select_state]]

            if relay is not None:
                # Print the pin, current value and time and date of the pin change event.
                self.logger.debug(f'{relay} current={sense_value}')
                relay.sensed_current.append(sense_value)
        except Exception as e:
            self.logger.error(f'{sense_pin} {sense_value} {e!r}')

    def _format_time(self, t0, str_format='%Y-%m-%d %H:%M:%S'):
        return time.strftime(str_format, time.localtime(t0))

    def __str__(self):
        return f'Power Distribution Board - {self.name}'

    def __del__(self):
        self.logger.debug(f'Shutting down power board.')
        self.board.shutdown()


class Relay(PanBase):
    """A relay object."""

    def __init__(self, board, pin_number, name, label=None, initial_state=PinState.LOW, sensing_enabled=True,
                 sensing_pin=None, *args, **kwargs):
        """Initialize a relay object."""

        super().__init__(*args, **kwargs)
        self.board = board
        self.pin_number = pin_number
        self.name = name

        self.label = None
        self.set_label(label, save=False)

        # Flexible entry types for initial state.
        self.initial_state = initial_state
        if self.initial_state is None:
            self.initial_state = PinState.LOW
        else:
            if type(self.initial_state) == 'str':
                # See if a pin label.
                with suppress(KeyError):
                    self.initial_state = PinState[self.initial_state.upper()]
            else:
                with suppress(ValueError):
                    self.initial_state = PinState(self.initial_state)

        self.state = None
        self.sensed_current = deque(list(), 100)

        self.sensing_enabled = sensing_enabled
        self.sensing_pin = sensing_pin

        if type(self.initial_state) == PinState:
            self.logger.info(f'{self.name} setting initial state to {self.initial_state}')
            self.board.digital_write(self.pin_number, self.initial_state.value)
            self.state = self.initial_state

    def turn_on(self):
        """Sets the relay to PinState.HIGH"""
        self.logger.info(f'Turning {self.label} on.')
        self.board.digital_write(self.pin_number, PinState.HIGH.value)
        self.state = PinState.HIGH

    def turn_off(self):
        """Sets the relay to PinState.LOW"""
        self.logger.info(f'Turning {self.label} off.')
        self.board.digital_write(self.pin_number, PinState.LOW.value)
        self.state = PinState.LOW

    def toggle(self, delay=1):
        """Toggles the relay with a delay."""
        original_state = self.state
        temp_state = not original_state
        self.logger.info(f'{self} - Toggling from {original_state} with {delay} second delay')
        self.board.digital_write(self.pin_number, temp_state)
        time.sleep(delay)
        self.board.digital_write(self.pin_number, original_state)

    def set_label(self, label, save=False):
        """Sets the label for the relay and optionally save back to the config.

        Args:
            label (str): The label for the pin.
            save (bool): Save the new label to the config, default True.
        """
        self.label = label
        if save:
            self.set_config(f'environment.power.relays.{self.name}.label', label)
            self.logger.info(f'Saved relay={self.name} label={label} to pin_number={self.pin_number}')

    def __str__(self):
        return f'{self.label:12s} [{self.name} {self.pin_number:02d}] - {self.state}'
