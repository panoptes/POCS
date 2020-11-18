from contextlib import suppress
import time
from enum import IntEnum
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
    RELAY_0 = 17  # Analog 3
    RELAY_1 = 3
    RELAY_2 = 4
    RELAY_3 = 7
    RELAY_4 = 8


class CurrentSensePins(IntEnum):
    """Pins on which the current can be read."""
    IS_0 = 0  # Analog 0
    IS_1 = 1  # Analog 1
    IS_2 = 2  # Analog 2


class CurrentSelectPins(IntEnum):
    """Pins for selecting current sensing channel of a PROFET."""
    DSEL_0 = 2
    DSEL_1 = 6


class CurrentEnablePins(IntEnum):
    """Pins for enabling the current sensing."""
    DEN_0 = 18  # Analog 4
    DEN_1 = 5
    DEN_2 = 9


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
        self.relays = relays or self.config.get('relays', dict())

        # Set up the PymataExpress board.
        self.logger.debug(f'Setting up Power board connection')
        self.board = pymata4.Pymata4(arduino_instance_id=arduino_instance_id)

        # Set initial pin modes.
        self.set_pin_modes()

        # Enable current sensing.
        self.logger.debug(f'Turning on current sensing')
        for pin_number in CurrentEnablePins:
            self.set_pin_state(pin_number, PinState.HIGH)

        # Set initial pin states.
        self.logger.debug(f'Setting initial relay states')
        for relay_name, relay_config in self.relays.items():
            label = relay_config['label']
            initial_state = relay_config.get('initial_state', 'off').upper()

            self.set_pin_state(RelayPins[relay_name], initial_state)

            # Set an attribute with the relay label for easy access.
            self.set_relay_name(RelayPins[relay_name], label)

        self.logger.success(f'Power board initialized')

    def set_relay_name(self, number, name):
        """Sets an attribute with the given name that returns the pin number.

        Args:
            number (int): The pin number to set an attribute name for.
            name (str): The name for the pin.
        """
        self.logger.debug(f'Adding {name} as board attribute with pin_number={number}')
        setattr(self, name, number)

    def set_pin_modes(self, analog_callback=None, analog_differential=1):
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

        self.logger.debug(f'Setting up analog pins for reading current')
        for pin in CurrentSensePins:
            self.board.set_pin_mode_analog_input(pin.value,
                                                 callback=analog_callback,
                                                 differential=analog_differential)

        self.logger.debug(f'Setting up current enable pins')
        for pin in CurrentEnablePins:
            self.board.set_pin_mode_digital_output(pin.value)

        self.logger.debug(f'Setting up relay pins')
        for pin in RelayPins:
            self.board.set_pin_mode_digital_output(pin.value)

        self.logger.debug(f'Setting up current select pins')
        for pin in CurrentSelectPins:
            self.board.set_pin_mode_digital_output(pin.value)

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
        self.logger.debug(f'Setting digital pin {pin_number} to {state}')
        self.board.digital_write(pin_number, state)

        return True

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

    def turn_on(self, relay_name):
        """Turns off the given power relay.

        Note: This method is not asynchronous.

        Args:
            relay_name (str): The name of the relay to turn on.
        """
        self.logger.info(f'Turning on {relay_name}')
        pin_number = getattr(self, relay_name)
        return self.set_pin_state(pin_number, PinState.HIGH)

    def turn_off(self, relay_name):
        """Turns off the given power relay.

        Note: This method is not asynchronous.

        Args:
            relay_name (str): The name of the relay to turn off.
        """
        self.logger.info(f'Turning off {relay_name}')
        pin_number = getattr(self, relay_name)
        return self.set_pin_state(pin_number, PinState.LOW)

    def toggle(self, relay_name, delay=0.5):
        """Toggles the power state with optional delay.

        Args:
            relay_name (str): The name of the relay to toggle.
            delay (int): The delay between toggling the state in seconds.
        """
        pin_number = getattr(self, relay_name)
        starting_state = self.get_pin_state(pin_number)
        self.logger.info(f'Toggling {relay_name} (with {delay} ms delay). '
                         f'Starting state = {starting_state}')

        self.set_pin_state(pin_number, not starting_state)
        time.sleep(delay)
        self.set_pin_state(pin_number, starting_state)

    def read_current(self, record=False):
        """Reads the current from all relays on the board.

        The Power Board uses the Infineon 24V relay shield, which has five
        relays but only three MOSFETs (actually a PROFET). To read the current,
        we poll the two MOSFETs with shared relays, change which relay is read,
        and then poll again.  The third MOSFET is polled each time and averaged.

        This will first set the channel select pins to low, do a reading,
        then set to high and do another reading.

        Args:
            record (bool): If entry should be saved to metadata database, default False.

        Returns:
            dict: A dictionary containing the current readings for each relay.
        """
        # Set select pins to low.
        self.set_pin_state(CurrentSelectPins.DSEL_0, PinState.LOW)
        self.set_pin_state(CurrentSelectPins.DSEL_1, PinState.LOW)

        # Read current.
        relay_0_value, relay_0_timestamp = self.board.analog_read(CurrentSensePins.IS_0.value)
        relay_2_value, relay_2_timestamp = self.board.analog_read(CurrentSensePins.IS_1.value)

        # Set select pins to low.
        self.set_pin_state(CurrentSelectPins.DSEL_0, PinState.HIGH)
        self.set_pin_state(CurrentSelectPins.DSEL_1, PinState.HIGH)

        # FirmataExpress polls analog pins every 19 ms, delay 500 ms before reading.
        time.sleep(0.5)

        # Read current.
        relay_1_value, relay_1_timestamp = self.board.analog_read(CurrentSensePins.IS_0.value)
        relay_3_value, relay_3_timestamp = self.board.analog_read(CurrentSensePins.IS_1.value)

        relay_4_value, relay_4_timestamp = self.board.analog_read(CurrentSensePins.IS_2.value)

        current_readings = {
            self.relays['RELAY_0']['label']: (relay_0_value, self._format_time(relay_0_timestamp)),
            self.relays['RELAY_1']['label']: (relay_1_value, self._format_time(relay_1_timestamp)),
            self.relays['RELAY_2']['label']: (relay_2_value, self._format_time(relay_2_timestamp)),
            self.relays['RELAY_3']['label']: (relay_3_value, self._format_time(relay_3_timestamp)),
            self.relays['RELAY_4']['label']: (relay_4_value, self._format_time(relay_4_timestamp)),
        }

        self.logger.debug(f'Current readings: {current_readings!r}')
        self.db.insert_current('power', dict(current=current_readings))

        return current_readings

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
        self.logger.debug(f'Callback: {data!r}')
        pin_mode_lookup = {0: 'digital', 2: 'analog', 11: 'digital_pullup'}

        # Convert the date stamp to readable format
        pin_mode = pin_mode_lookup[data[0]]
        pin_number = data[1]
        value = data[2]
        timestamp = self._format_time(data[3])

        select0_state = self.get_pin_state(CurrentSelectPins.DSEL_0)
        select1_state = self.get_pin_state(CurrentSelectPins.DSEL_1)

        which_relay = None

        if select0_state == PinState.LOW:
            which_relay = RelayPins.RELAY_0
        else:
            which_relay = RelayPins.RELAY_1

        if select1_state == PinState.LOW:
            which_relay = RelayPins.RELAY_2
        else:
            which_relay = RelayPins.RELAY_3

        # Print the pin, current value and time and date of the pin change event.
        self.logger.debug(f'Relay: {which_relay} Value: {value} Time Stamp: {timestamp} Pin: ({pin_mode} {pin_number})')

    def _format_time(self, t0, format='%Y-%m-%d %H:%M:%S'):
        return time.strftime(format, time.localtime(t0))

    def __str__(self):
        return f'Power Distribution Board - {self.name}'

    def __del__(self):
        self.logger.debug(f'Shutting down power board.')
        self.board.shutdown()
