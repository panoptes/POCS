import threading
from enum import IntEnum
from dataclasses import dataclass
from typing import Optional
from collections import deque
import numpy as np

from panoptes.utils.rs232 import SerialData, get_serial_port_info
from panoptes.utils.serializers import from_json
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
    TOGGLE = 3  # Toggle relay.
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
    default_state: Optional[PinState] = PinState.OFF
    multiplier: Optional[float] = 1.0

    @property
    def current(self):
        """Gets the mean of the current entries"""
        return np.mean(self.current_readings)

    @property
    def status(self):
        return dict(state=self.state, current=self.current)

    def __str__(self):
        return f'[{self.name}] {self.label}: {self.state.name} {self.current}'


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

    def __init__(self, port=None, name='Power Board', relays=None, *args, **kwargs):
        """Initialize the power board.

        The `relays` should be a dictionary with the relay name as key and a
        dict with `label` and `initial_state` entries::

            RELAY_0:
                label: mount
                initial_state: on

        Args:
            port (str, optional): The dev port for the arduino, if not provided, search for port
                matching the vendor (2341) and product id (0043).
            name (str): The user-friendly name for the power board.
            relays (dict[Relay] or None): The relay configuration. See notes for details.
        """
        super().__init__(*args, **kwargs)
        if port is None:
            port = PowerBoard.guess_port()
            self.logger.info(f'Guessing that arduino is on {port=}')

        self.port = port
        self.name = name

        self.logger.debug(f'Setting up Power board connection for {name=} on {self.port}')
        self.arduino_board = SerialData(port=self.port, baudrate=9600)
        self.alive = False
        self._reader_thread = None
        self._reader_alive = None
        self._read_buffer = bytearray()

        self.relay_labels = dict()
        self.relays = dict()
        self.setup_relays(relays, queue_maxsize=25)

        # Set initial relay states.
        for relay in self.relays.values():
            self.change_relay_state(relay, relay.state)

        self.start_reading_status()

        self.logger.success(f'Power board initialized')

    def turn_on(self, label):
        """Turns on the relay with the given label."""
        self.change_relay_state(self.relay_labels[label], PinState.ON)

    def turn_off(self, label):
        """Turns off the relay with the given label."""
        self.change_relay_state(self.relay_labels[label], PinState.OFF)

    def setup_relays(self, relays, queue_maxsize=25):
        """Setup the relays."""
        for relay_name, relay_config in relays.items():
            relay_index = TruckerRelayIndex[relay_name]
            relay_label = relay_config.get('label') or relay_name
            default_state = PinState[relay_config.get('default_state', 'off').upper()]

            # Create relay object.
            self.logger.debug(f'Creating {relay_label=} for {relay_config!r}')
            relay = Relay(name=relay_name,
                          label=relay_config.get('label', ''),
                          relay_index=relay_index,
                          current_readings=deque(maxlen=queue_maxsize),
                          default_state=default_state
                          )

            # Track relays by name and friendly label.
            self.relays[relay.name] = relay
            self.relay_labels[relay.label] = relay

            self.logger.info(f'{relay.label} added to board')

        self.logger.success(f'Relays: {self.relays!r}')

    def change_relay_state(self, relay: Relay, new_state: PinState):
        """Changes the relay to the new state. """
        new_state_command = TruckerBoardCommands[new_state.name]
        # Must have the newline in command.
        write_command = f'{relay.relay_index.value},{new_state_command.value}\n'
        self.logger.debug(f'Sending relay state change command to board: {write_command!r}')
        self.arduino_board.write(write_command)

    def start_reading_status(self):
        """Start the read loop."""
        self.logger.info('Starting status reading thread.')
        self.alive = True
        self._start_reader()

    def stop_reader(self):
        """Stop reader only, wait for clean exit of thread."""
        self._reader_alive = False
        if hasattr(self.arduino_board.ser, 'cancel_read'):
            self.arduino_board.ser.cancel_read()
        self.receiver_thread.join()

    def _read_status(self):
        """Continuously read the status from the arduino and insert into deque for relay."""
        try:
            while self.alive and self._reader_alive:
                # Look for a complete line and return if so.
                i = self._read_buffer.find(b"\r\n")
                if i >= 0:
                    raw_reading = self._read_buffer[:i + 2]
                    self._read_buffer = self._read_buffer[i + 2:]
                else:
                    # Otherwise keep reading until we get a newline.
                    while True:
                        i = max(1, min(2048, self.arduino_board.ser.in_waiting))
                        data = self.arduino_board.ser.read(i)
                        i = data.find(b"\r\n")
                        if i >= 0:
                            raw_reading = self._read_buffer + data[:i + 2]
                            self._read_buffer[0:] = data[i + 2:]
                            break
                        else:
                            self._read_buffer.extend(data)

                raw_data = raw_reading.decode()
                for reading in raw_data.split('\r\n'):
                    if reading == '':
                        continue
                    try:
                        data = from_json(reading)
                    except error.InvalidDeserialization:
                        self.logger.warning(f'Cannot deserialize reading from arduino: {reading!r}')
                    else:
                        # Record the current.
                        currents = data.get('currents', list())
                        for i, val in enumerate(currents):
                            relay = self.relays[TruckerRelayIndex(i).name]
                            relay.current_readings.append(val * relay.multiplier)

                        # Update the state for the relay.
                        relay_status = data.get('relays', list())
                        for i, val in enumerate(relay_status):
                            self.relays[TruckerRelayIndex(i).name].state = PinState(val)
        except error.BadSerialConnection as e:
            self.logger.error(e)
            self.alive = False
            raise e

    def _start_reader(self):
        """Start status reader thread."""
        self._reader_alive = True
        self.receiver_thread = threading.Thread(target=self._read_status, name='status_reader')
        self.receiver_thread.daemon = True
        self.receiver_thread.start()

    def __str__(self):
        relay_states = ' '.join([f'{r.name}: {r.state.name}' for r in self.relays.values()])
        return f'{self.name} - {relay_states}'

    @classmethod
    def guess_port(cls, vendor_id=0x2341, product_id=0x0043, return_all=False):
        """Tries to guess the port hosting the power board arduino.

        The default vendor_id is for official Arduino products. The default product_id
        is for an Uno Rev 3.

        https://github.com/arduino/Arduino/blob/1.8.0/hardware/arduino/avr/boards.txt#L51-L58

        """
        # Get all serial ports.
        arduino_ports = [p for p in get_serial_port_info() if
                         p.vid == vendor_id and p.pid == product_id]

        if len(arduino_ports) == 1:
            return arduino_ports[0].device
        elif return_all:
            return arduino_ports
        else:
            raise error.NotFound(f'No official arduino devices found.')
