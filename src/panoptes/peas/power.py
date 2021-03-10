import asyncio
import threading
import time
from enum import IntEnum
from dataclasses import dataclass
from typing import Optional
from functools import partial
from collections import deque

import numpy as np
from panoptes.utils.rs232 import SerialData
from panoptes.utils.serializers import from_json
from streamz import Stream
from panoptes.pocs.base import PanBase
from panoptes.utils import error


class PinState(IntEnum):
    """Represents a HIGH or LOW state for a digital output pin."""
    OFF = 0
    LOW = 0
    ON = 1
    HIGH = 1


class TruckerBoardCommands(IntEnum):
    """The Trucker Board can accept a series of commands for controlling the relays"""
    ON = 1
    OFF = 2
    TOGGLE = 3  # Toggle current state.
    CYCLE_DELAY = 4  # Cycle the current state with a 30 second delay.


class TruckerRelayIndex(IntEnum):
    """The available relays on the Trucker Board"""
    RELAY_0 = 0
    RELAY_1 = 1
    RELAY_2 = 2
    RELAY_3 = 3
    RELAY_4 = 4


@dataclass
class Relay:
    """Relay data class"""
    name: str
    label: Optional[str]
    current_readings: deque
    relay_index: TruckerRelayIndex
    state: Optional[PinState] = PinState.OFF


class PowerBoard(PanBase):
    """Power distribution and monitoring.

    This represents a "trucker" board for PANOPTES, which is a combination of an
    Arduino Uno and an Infineon 24V relay shield.

    The relay shield has three PROFETs on them that are capable of sensing the
    current through the relay. RELAY_4 has a dedicated PROFET. The other two
    PROFETs can switch between two relays depending on the status of the appropriate
    DSEL pin.

    Pin names specified above correspond to Infineon terminology. See manual:
    https://bit.ly/2IGgWLQ.
    """

    def __init__(self, port, name='Power Board', relays=None, *args, **kwargs):
        """Initialize the power board.

        The `relays` should be a dictionary with the relay name as key and a
        dict with `label` and `initial_state` entries::

            RELAY_0:
                label: mount
                initial_state: on

        Args:
            port (str): The dev port for the arduino.
            name (str): The user-friendly name for the power board.
            relays (dict[Relay] or None): The relay configuration. See notes for details.
        """
        super().__init__(*args, **kwargs)
        self.name = name

        # Set up a processing stream to do a sliding median on the sensed current.
        # self._current_stream = self._build_stream()

        self.logger.debug(f'Setting up Power board connection')
        self.arduino_board = SerialData(port=port, baudrate=9600)
        self.alive = False
        self._reader_thread = None
        self._reader_alive = None

        self.relay_labels = dict()
        self.relays = dict()
        self.setup_relays(relays)

        # Set initial relay states.
        for relay in self.relays.values():
            self.change_relay_state(relay, relay.state)

        self.start_reading_current()

        self.logger.success(f'Power board initialized')

    def start_reading_current(self):
        """Start the read loop."""
        self.alive = True
        self._start_reader()

    def turn_on(self, label):
        """Turns on the relay with the given label."""
        self.change_relay_state(self.relay_labels[label], PinState.ON)

    def turn_off(self, label):
        """Turns off the relay with the given label."""
        self.change_relay_state(self.relay_labels[label], PinState.OFF)

    def setup_relays(self, relays):
        """Set the relays"""
        for relay_name, relay_config in relays.items():
            relay_index = TruckerRelayIndex(relay_name)
            relay_label = relay_config.get('label') or relay_name
            initial_state = PinState[relay_config.get('initial_state', 'off').upper()]

            # Create relay object.
            self.logger.debug(f'Creating {relay_label=} for {relay_config!r}')
            relay = Relay(name=relay_name,
                          label=relay_config.get('label', ''),
                          relay_index=relay_index,
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
        new_state_command = TruckerBoardCommands[new_state.name]
        self.arduino_board.write(f'{relay.relay_index},{new_state_command.value}')
        relay.state = new_state

    def _read_currents(self):
        """Continuously read the current from the arduino"""
        try:
            while self.alive and self._reader_alive:
                raw_data = self.arduino_board.ser.read(self.arduino_board.ser.in_waiting or 1)
                if raw_data:
                    data = from_json(raw_data.decode('ascii'))
                    # TODO send text downstream
                    #     # Send downstream.
                    #     self._current_stream.emit(data)
        except error.BadSerialConnection as e:
            self.alive = False
            raise

    def _start_reader(self):
        """Start reader thread."""
        self._reader_alive = True
        self.receiver_thread = threading.Thread(target=self._read_currents, name='current_reader')
        self.receiver_thread.daemon = True
        self.receiver_thread.start()

    def _stop_reader(self):
        """Stop reader only, wait for clean exit of thread."""
        self._reader_alive = False
        if hasattr(self.arduino_board.ser, 'cancel_read'):
            self.arduino_board.ser.cancel_read()
        self.receiver_thread.join()

    #
    # def _build_stream(self):
    #     """Build a stream for processing the analog readings.
    #
    #     The stream will receive a dict with 'relay', 'value', and 'timestamp'.
    #
    #     Returns:
    #         streamz.Stream: A processing stream.
    #     """
    #     stream = Stream()
    #
    #     def filter_streams(reading, relay):
    #         """Split stream based on which relay was sensed."""
    #         return reading['relay'] == relay
    #
    #     split_streams = [
    #         stream.filter(partial(filter_streams, relay=relay))
    #         for relay in SENSE_ENABLED_RELAY_LOOKUP.values()
    #     ]
    #
    #     def get_sliding_value(readings):
    #         # All the same relay, grab first.
    #         relay = readings[0]['relay']
    #         sliding_median = np.median([r['value'] for r in readings])
    #         return dict(relay=relay, value=sliding_median)
    #
    #     # Run a sliding mean on each relay stream.
    #     sliding_streams = [
    #         stream.sliding_window(10, return_partial=False).map(get_sliding_value)
    #         for stream in split_streams
    #     ]
    #
    #     def update_relay(reading):
    #         relay = reading['relay']
    #         value = reading['value']
    #         relay.current_readings.append(value)
    #
    #     Stream.union(*sliding_streams).sink(update_relay)
    #
    #     return stream

    def __str__(self):
        return f'{self.name} - {[relay.state for relay in self.relays]}'
