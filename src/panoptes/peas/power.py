import time
from contextlib import suppress
from enum import IntEnum

from pymata_express import pymata_express

from panoptes.pocs.base import PanBase


class PinState(IntEnum):
    LOW = 0
    HIGH = 1


class PowerBoard(PanBase):
    """Power distribution and monitoring"""

    def __init__(self, name='Power Board', arduino_instance_id=None, channels=None, pins=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.name = name

        # Lookup config for power board.
        self.config = self.get_config('environment.power')

        arduino_instance_id = arduino_instance_id or self.config.get('arduino_instance_id', default=1)
        self.channels = channels or self.config.get('channels', default=dict())

        # Get the pin mapping from the config if not provided.
        self.pin_mapping = pins or self.config.get('pins', default=dict())

        # Set up the PymataExpress board.
        self.logger.debug(f'Setting up Power board connection')
        self.board = pymata_express.PymataExpress(arduino_instance_id=arduino_instance_id)

        self.setup_pins()

        self.logger.success(f'Power board')

    def setup_pins(self, analog_pins=None, digital_pins=None):
        """Set the pin modes.

        Args:
            analog_pins (dict or None): Analog pin mapping. If not provided,
                uses 'analog' pins from `self.pin_mapping`.
            digital_pins (dict or None): Digital pin mapping. If not provided,
                uses 'digital' pins from `self.pin_mapping`.
        """
        digital_pins = digital_pins or self.pin_mapping['digital']
        analog_pins = analog_pins or self.pin_mapping['analog']

        self.logger.debug(f'Setting analog pins for {self.name}')
        for pin_number, pin_name in analog_pins:
            self.logger.debug(f'Setting pin_number={pin_number} as analog input.')
            await self.board.set_pin_mode_analog_input(pin_number)

        # All our pins are output on PowerBoard.
        self.logger.debug(f'Setting digital pin for {self.name}')
        for pin_number, pin_config in digital_pins:
            pin_mode = pin_config['mode']
            pin_name = pin_config['name']
            initial_pin_state = pin_config['initial']

            self.logger.debug(f'Setting digital pin_number={pin_number} ({pin_name}) as {pin_mode}')
            await self.board.set_pin_mode_digital_output(pin_number)

            # Set up attribute if pin is a relay channel.
            with suppress(KeyError):
                channel_name = self.channels[pin_name]
                if channel_name != 'unused':
                    self.set_pin_name(pin_number, channel_name)

            # Set initial state on digital output pin.
            self.set_pin_state(pin_number, initial_pin_state)

    def set_pin_name(self, number, name):
        """Sets an attribute with the given name that returns the pin number.

        Args:
            number (int): The pin number to set an attribute name for.
            name (str): The name for the pin.
        """
        self.logger.debug(f'Adding {name} as board attribute with pin_number={number}')
        setattr(self, name, number)

    def get_channel_pin(self, name):
        """Get the pin number for the given channel name.

        Args:
            name (str): The name of the 'channel' to turn on.

        Returns:
            int: The pin number corresponding to name for the channel.
        """
        try:
            pin_name = self.config['channels'][name]
            pin_number = getattr(self, pin_name)
        except (KeyError, AttributeError):
            self.logger.warning(f'No pin found for {name}')
            return False

        self.logger.debug(f'Return pin_number={pin_number} for {name}')

        return pin_number

    def get_pin_state(self, channel_name):
        """Get the digital pin state.

        Args:
            channel_name (str): The name of the channel to read state from.

        Returns:
            bool: True if pin is HIGH, False if LOW.
        """
        pin_number = self.get_channel_pin(channel_name)
        state, timestamp = await self.board.digital_read(pin_number)
        self.logger.info(f'{channel_name} = {state} (at {timestamp})')

        return bool(state)

    def set_pin_state(self, pin_number, state):
        """Turns on the power channel with the given name.

        Args:
            pin_number (int): The pin number of the channel to turn on.
            state (bool): A state that evaluates to True for "on" and False for "off".

        Returns:
            bool: True if pin state successfully set.
        """
        state = bool(state)
        self.logger.debug(f'Setting digital pin {pin_number} to {state}')
        await self.board.digital_write(pin_number, state)

        return True

    def turn_on(self, channel_name):
        """Turns off the given power channel.

        Note: This method is not asynchronous.

        Args:
            channel_name (str): The name of the channel to turn on.
        """
        self.logger.info(f'Turning on {channel_name}')
        return await self.set_pin_state(channel_name, PinState.HIGH)

    def turn_off(self, channel_name):
        """Turns off the given power channel.

        Note: This method is not asynchronous.

        Args:
            channel_name (str): The name of the channel to turn off.
        """
        self.logger.info(f'Turning off {channel_name}')
        return await self.set_pin_state(channel_name, PinState.LOW)

    def toggle(self, channel_name, delay=500):
        """Toggles the power state with optional delay.

        Args:
            channel_name (str): The name of the channel to toggle.
            delay (int): The delay between toggling the state in milliseconds.
        """
        starting_state = self.get_pin_state(channel_name)
        self.logger.info(f'Toggling {channel_name} (with {delay} ms delay). '
                         f'Starting state = {starting_state}')

        self.set_pin_state(channel_name, not starting_state)
        time.sleep(delay)
        self.set_pin_state(channel_name, starting_state)

    def __str__(self):
        return f'Power Distribution Board - {self.name}'

    def __del__(self):
        self.board.shutdown()
