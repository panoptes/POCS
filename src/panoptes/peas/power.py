import asyncio
import time
from enum import IntEnum
from dataclasses import dataclass
from typing import Optional
from functools import partial
from collections import deque

import numpy as np
from pymata_express import pymata_express
from streamz import Stream
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
    """Analog pins on which the current can be read.

    The [] below indicates the disabled relays w.r.t current sensing.
    See the PowerBoard docs.
    """
    IS_0 = 0  # A0 - Sensing for RELAY_0 [or RELAY_1]
    IS_1 = 1  # A1 - Sensing for RELAY_2 [or RELAY_3]
    IS_2 = 2  # A2 - Sensing for RELAY_4


class CurrentSelectPins(IntEnum):
    """Digital output pins for selecting current sensing channel of a PROFET.

    The [] below indicates the disabled relays w.r.t current sensing.
    See the PowerBoard docs.
    """
    DSEL_0 = 2  # LOW for RELAY_0, [HIGH for RELAY_1]
    DSEL_1 = 6  # LOW for RELAY_2, [HIGH for RELAY_3]


class CurrentEnablePins(IntEnum):
    """Pins for enabling the current sensing.

    The [] below indicates the disabled relays w.r.t current sensing.
    See the PowerBoard docs.
    """
    DEN_0 = 18  # A4 - Enable RELAY_0 [and RELAY_1]
    DEN_1 = 5  # Enable RELAY_2 [and RELAY_3]
    DEN_2 = 9  # Enable RELAY_4


# This is a simple lookup because we are restricting the relays that can be sensed.
SENSE_ENABLED_RELAY_LOOKUP = {
    CurrentSensePins.IS_0: RelayPins.RELAY_0,
    CurrentSensePins.IS_1: RelayPins.RELAY_2,
    CurrentSensePins.IS_2: RelayPins.RELAY_4,
}


@dataclass
class Relay:
    """Relay data class"""
    name: str
    pin_number: int
    label: Optional[str]
    current_readings: deque
    state: Optional[PinState] = PinState.OFF


class PowerBoard(PanBase):
    """Power distribution and monitoring.

    This represents a "trucker" board for PANOPTES, which is a combination of an
    Arduino Uno and an Infineon 24V relay shield.

    The relay shield has three PROFETs on them that are capable of sensing the
    current through the relay. RELAY_4 has a dedicated PROFET. The other two
    PROFETs can switch between two relays depending on the status of the appropriate
    DSEL pin.

    The arduino is currently using FirmataExpress so that the logic can be controlled
    from the client (python; this file) side. This provides various benefits, such
    as auto-discovery of the arduino as well as efficient IO.  However, it makes
    it difficult (although not impossible) to implement properly on the client
    side.  For now we simply restrict current sensing to a single relay per PROFET.
    For simplicity these are RELAY_0, RELAY_2, and RELAY_4.

        RELAY_0──DSEL_0_HIGH───IS_0  DEN_0_HIGH

        RELAY_1───DSEL_0_LOW────IS_0  DEN_0_HIGH  [CURRENTLY DISABLED]

        RELAY_2───DSEL_1_HIGH───IS_1  DEN_1_HIGH

        RELAY_3───DSEL_1_LOW────IS_1  DEN_1_HIGH  [CURRENTLY DISABLED]

        RELAY_4─────────────────IS_2  DEN_2_HIGH

    Pin names specified above correspond to Infineon terminology. See manual:
    https://bit.ly/2IGgWLQ.
    """

    def __init__(self,
                 name='Power Board',
                 relays=None,
                 arduino_instance_id=1,
                 analog_differential=5,
                 *args, **kwargs):
        """Initialize the power board.

        The `relays` should be a dictionary with the relay name as key and a
        dict with `label` and `initial_state` entries::

            RELAY_0:
                label: mount
                initial_state: on

        Args:
            name (str): The user-friendly name for the power board.
            relays (dict[Relay] or None): The relay configuration. See notes for details.
                A default value of None will attempt to look up relays in the
                config-server.
            arduino_instance_id (int or None): If multiple arduinos are present
                on the system the specific board can be specified with this parameter.
                Requires setting the instance_id in the arduino sketch before upload.
                If None, pymata will attempt auto-discovery of the arduinos.
            analog_differential (int): Analog values are only reported if they differ from the
                previous value by this amount, default 5 of 1023.
        """
        super().__init__(*args, **kwargs)
        self.name = name

        # Set up a processing stream to do a sliding median on the sensed current.
        self._current_stream = self._build_stream()

        # Set up the PymataExpress board.
        self.logger.debug(f'Setting up Power board connection')
        self.event_loop = asyncio.get_event_loop()
        self.arduino_board = pymata_express.PymataExpress(arduino_instance_id=arduino_instance_id)

        self.relay_labels = dict()
        self.relays = dict()
        self.setup_relays(relays)

        # Set initial pin modes.
        self.event_loop.run_until_complete(self.set_pin_modes(analog_differential=analog_differential))

        # Set initial relay states.
        for relay in self.relays.values():
            self.change_relay_state(relay, relay.state)

        self.logger.success(f'Power board initialized')

    def turn_on(self, label):
        """Turns on the relay with the given label."""
        self.change_relay_state(self.relay_labels[label], PinState.ON)

    def turn_off(self, label):
        """Turns off the relay with the given label."""
        self.change_relay_state(self.relay_labels[label], PinState.OFF)

    def setup_relays(self, relays):
        """Set the relays"""
        self.logger.debug(f'Setting initial relay states')
        for relay_name, relay_config in relays.items():
            relay_label = relay_config.get('label') or relay_name
            initial_state = PinState[relay_config.get('initial_state', 'off').upper()]

            # Create relay object.
            self.logger.debug(f'Creating {relay_label=} for {relay_config!r}')
            relay = Relay(pin_number=RelayPins[relay_name].value,
                          name=relay_name,
                          label=relay_config.get('label', ''),
                          current_readings=deque(maxlen=10),
                          state=initial_state
                          )

            # Track relays by name and friendly label.
            self.relays[relay.name] = relay
            self.relay_labels[relay.label] = relay

            self.logger.info(f'{relay.label} added to board')

        self.logger.success(f'Relays: {self.relays!r}')

    def change_relay_state(self, relay, new_state):
        """Changes the relay to the new state.

        Note: This waits for the async calls to finish.
        """
        self.event_loop.run_until_complete(self.set_pin_state(relay.pin_number, new_state.value))
        relay.state = new_state

    async def set_pin_state(self, pin_number, state):
        """Set the relay to the given state.

        Args:
            pin_number (int): The pin number of the relay to turn on.
            state (bool or int): True for PinState.ON, False for PinState.OFF.
        """
        self.logger.debug(f'Setting digital output pin={pin_number} to {state=}')
        await self.arduino_board.digital_write(pin_number, state)

    async def get_pin_state(self, pin_number):
        """Get the digital pin state.

        Args:
            pin_number (int): The pin number read state from.

        Returns:
            int: The PinState of the pin.
        """
        state, timestamp = await self.arduino_board.digital_read(pin_number)
        self.logger.info(f'{pin_number=} {state=} {timestamp=}')

        return state

    async def _analog_callback(self, data):
        """Send analog values downstream for processing.

        See: https://mryslab.github.io/pymata-express/

        Args:
            data (list): A list containing: [pin_type=2, pin=[0,1,2], value, timestamp]
        """
        sensed_pin = data[1]
        relay = SENSE_ENABLED_RELAY_LOOKUP[CurrentSensePins(sensed_pin)]
        sensed_value = data[2]
        timestamp = data[3]

        data = dict(relay=relay, value=sensed_value, timestamp=timestamp)

        # Send downstream.
        self._current_stream.emit(data)

    async def set_pin_modes(self, analog_callback=None, analog_differential=5):
        """Set the pin modes for the Arduino Uno + Infineon Uno 24V shield.

        An optional callback can be specified for the analog input pins. This
        callback should accept a single parameter that will be populated with a
        list containing: [pin, current reported value, pin_mode, timestamp].

        Args:
            analog_differential (int): Input values are only reported if the difference
                between the current value and the previous exceeds the differential.
                Default value is 5 (of 1023).
            analog_callback (callable): The callback for reading the analog input
                pins. See above for details. If no callback is specified the default
                `self.analog_callback` is used.
        """
        if analog_callback is None:
            analog_callback = self._analog_callback

        # Set up relays so they can be turned on and off.
        for pin in RelayPins:
            self.logger.info(f'Setting relay {pin=} as digital output')
            await self.arduino_board.set_pin_mode_digital_output(pin.value)

        # Enable current sensing on all PROFETs.
        for pin in CurrentEnablePins:
            self.logger.info(f'Setting current enable {pin=} as digital output with state=high')
            await self.arduino_board.set_pin_mode_digital_output(pin.value)
            await self.set_pin_state(pin.value, PinState.HIGH)

        # Set to LOW to enable RELAY_0 and RELAY_4.
        for pin in CurrentSelectPins:
            self.logger.info(f'Setting current select {pin=} as digital output with state=low')
            await self.arduino_board.set_pin_mode_digital_output(pin.value)
            await self.set_pin_state(pin.value, PinState.LOW)

        # Start sensing!
        for pin in CurrentSensePins:
            self.logger.debug(f'Setting current sense {pin=} as analog input')
            await self.arduino_board.set_pin_mode_analog_input(pin.value,
                                                               callback=analog_callback,
                                                               differential=analog_differential)

    def shutdown(self):
        """Powers down the board"""
        self.event_loop.run_until_complete(self.arduino_board.shutdown())

    def _build_stream(self):
        """Build a stream for processing the analog readings.

        The stream will receive a dict with 'relay', 'value', and 'timestamp'.

        Returns:
            streamz.Stream: A processing stream.
        """
        stream = Stream()

        def filter_streams(reading, relay):
            """Split stream based on which relay was sensed."""
            return reading['relay'] == relay

        split_streams = [
            stream.filter(partial(filter_streams, relay=relay))
            for relay in SENSE_ENABLED_RELAY_LOOKUP.values()
        ]

        def get_sliding_value(readings):
            # All the same relay, grab first.
            relay = readings[0]['relay']
            sliding_median = np.median([r['value'] for r in readings])
            return dict(relay=relay, value=sliding_median)

        # Run a sliding mean on each relay stream.
        sliding_streams = [
            stream.sliding_window(10, return_partial=False).map(get_sliding_value)
            for stream in split_streams
        ]

        def update_relay(reading):
            relay = reading['relay']
            value = reading['value']
            relay.current_readings.append(value)

        Stream.union(*sliding_streams).sink(update_relay)

        return stream

    def _format_time(self, t0, str_format='%Y-%m-%d %H:%M:%S'):
        return time.strftime(str_format, time.localtime(t0))

    def __str__(self):
        return f'{self.name} - {[relay.state for relay in self.relays]}'
