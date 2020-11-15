import time
from enum import IntEnum

from pymata_express import pymata_express

from panoptes.pocs.base import PanBase


class PinState(IntEnum):
    """Represents a HIGH or LOW state for a digital output pin."""
    LOW = 0
    OFF = 0
    HIGH = 1
    ON = 1


class RelayPins(IntEnum):
    """The pins for the relays."""
    RELAY_0 = 17
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
    DEN_0 = 18
    DEN_1 = 5
    DEN_2 = 9


class PowerBoard(PanBase):
    """Power distribution and monitoring.

    This represents a "trucker" board for PANOPTES, which is a combination of an
    Arduino Uno and an Infineon 24V relay shield.

    Pin names specified above correspond to Infineon terminology. See manual:
    https://bit.ly/2IGgWLQ.
    """

    def __init__(self, name='Power Board', arduino_instance_id=None, relays=None, pins=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.name = name

        # Lookup config for power board.
        self.config = self.get_config('environment.power')

        arduino_instance_id = arduino_instance_id or self.config.get('arduino_instance_id', default=1)
        self.relays = relays or self.config.get('relays', default=dict())

        # Get the pin mapping from the config if not provided.
        self.pin_mapping = pins or self.config.get('pins', default=dict())

        # Set up the PymataExpress board.
        self.logger.debug(f'Setting up Power board connection')
        self.board = pymata_express.PymataExpress(arduino_instance_id=arduino_instance_id)

        # Set initial pin modes.
        self.set_pin_modes()

        # Set initial pin states.
        for relay_name, relay_config in self.relays:
            label = relay_config['label']
            initial_state = relay_config['initial_state'].upper()

            self.set_pin_state(RelayPins[relay_name], initial_state)

            # Set an attribute with the relay label for easy access.
            self.set_relay_name(RelayPins[relay_name], label)

        self.logger.success(f'Power board initialized')

    def set_pin_modes(self):
        """Set the pin modes for the Arduino Uno + Infineon Uno 24V shield."""
        self.logger.debug(f'Setting up current reading pins')
        for pin_number in CurrentSensePins:
            self.board.set_pin_mode_analog_input(pin_number)

        self.logger.debug(f'Setting up current enable pins')
        for pin_number in CurrentEnablePins:
            self.board.set_pin_mode_digital_output(pin_number)

        self.logger.debug(f'Setting up current select pins')
        for pin_number in CurrentSelectPins:
            self.board.set_pin_mode_digital_output(pin_number)

        self.logger.debug(f'Setting up relay pins')
        for pin_number in RelayPins:
            self.board.set_pin_mode_digital_output(pin_number)

    def set_pin_state(self, pin_number, state):
        """Set the relay to the given state.

        Args:
            pin_number (int): The pin number of the relay to turn on.
            state (bool or PinState): A state that evaluates to True for "on" and False for "off".

        Returns:
            bool: True if pin state successfully set.
        """
        state = PinState(bool(state))
        self.logger.debug(f'Setting digital pin {pin_number} to {state}')
        await self.board.digital_write(pin_number, state)

        return True

    def set_relay_name(self, number, name):
        """Sets an attribute with the given name that returns the pin number.

        Args:
            number (int): The pin number to set an attribute name for.
            name (str): The name for the pin.
        """
        self.logger.debug(f'Adding {name} as board attribute with pin_number={number}')
        setattr(self, name, number)

    def get_relay_state(self, relay_name):
        """Get the digital pin state.

        Args:
            relay_name (str): The name of the relay to read state from.

        Returns:
            bool: True if pin is HIGH, False if LOW.
        """
        pin_number = getattr(self, relay_name)
        state, timestamp = await self.board.digital_read(pin_number)
        self.logger.info(f'{relay_name} = {state} (at {timestamp})')

        return bool(state)

    def turn_on(self, relay_name):
        """Turns off the given power relay.

        Note: This method is not asynchronous.

        Args:
            relay_name (str): The name of the relay to turn on.
        """
        self.logger.info(f'Turning on {relay_name}')
        pin_number = getattr(self, relay_name)
        return await self.set_pin_state(pin_number, PinState.HIGH)

    def turn_off(self, relay_name):
        """Turns off the given power relay.

        Note: This method is not asynchronous.

        Args:
            relay_name (str): The name of the relay to turn off.
        """
        self.logger.info(f'Turning off {relay_name}')
        pin_number = getattr(self, relay_name)
        return await self.set_pin_state(pin_number, PinState.LOW)

    def toggle(self, relay_name, delay=0.5):
        """Toggles the power state with optional delay.

        Args:
            relay_name (str): The name of the relay to toggle.
            delay (int): The delay between toggling the state in seconds.
        """
        starting_state = self.get_relay_state(relay_name)
        self.logger.info(f'Toggling {relay_name} (with {delay} ms delay). '
                         f'Starting state = {starting_state}')

        pin_number = getattr(self, relay_name)
        self.set_pin_state(pin_number, not starting_state)
        time.sleep(delay)
        self.set_pin_state(pin_number, starting_state)

    def read_current(self):
        """Reads the current from all relays on the board.

        The Power Board uses the Infineon 24V relay shield, which has five
        relays but only three MOSFETs (actually a PROFET). To read the current,
        we poll the two MOSFETs with shared relays, change which relay is read,
        and then poll again.  The third MOSFET is polled each time and averaged.

        This will first set the channel select pins to low, do a reading,
        then set to high and do another reading.
        """
        # Set select pins to low.
        self.set_pin_state(CurrentSelectPins.DSEL_0, PinState.LOW)
        self.set_pin_state(CurrentSelectPins.DSEL_1, PinState.LOW)

        # Read current.
        relay_0_value, _ = self.board.digital_read(RelayPins.RELAY_0)
        relay_1_value, _ = self.board.digital_read(RelayPins.RELAY_1)

        # Set select pins to low.
        self.set_pin_state(CurrentSelectPins.DSEL_0, PinState.HIGH)
        self.set_pin_state(CurrentSelectPins.DSEL_1, PinState.HIGH)

        # FirmataExpress polls analog pins every 19 ms, delay 500 ms before reading.
        time.sleep(0.5)

        # Read current.
        relay_2_value, _ = self.board.digital_read(RelayPins.RELAY_2)
        relay_3_value, _ = self.board.digital_read(RelayPins.RELAY_3)

        relay_4_value, _ = self.board.digital_read(RelayPins.RELAY_4)

        current_readings = {
            self.relays['RELAY_0']['label']: relay_0_value,
            self.relays['RELAY_1']['label']: relay_1_value,
            self.relays['RELAY_2']['label']: relay_2_value,
            self.relays['RELAY_3']['label']: relay_3_value,
            self.relays['RELAY_4']['label']: relay_4_value,
        }

        self.db.insert_current('power', dict(current=current_readings))

    def __str__(self):
        return f'Power Distribution Board - {self.name}'

    def __del__(self):
        self.board.shutdown()
