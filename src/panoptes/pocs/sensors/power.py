import time
from enum import IntEnum
from dataclasses import dataclass
from typing import Optional, Dict, List, Callable
from functools import partial
import pandas as pd
from panoptes.utils import error

from streamz.dataframe import PeriodicDataFrame

from panoptes.utils.serial.device import find_serial_port, SerialDevice
from panoptes.utils.serializers import to_json, from_json
from panoptes.pocs.base import PanBase
from panoptes.utils.time import current_time


class PinState(IntEnum):
    """Represents a HIGH or LOW state for a digital output pin."""
    OFF = 0
    LOW = 0
    ON = 1
    HIGH = 1


POWER_SYMBOLS = {
    PinState.OFF: '⭘',
    PinState.ON: '⏽'
}


class TruckerBoardCommands(IntEnum):
    """The Trucker Board can accept a series of commands for controlling the relays"""
    OFF = 0
    ON = 1
    TOGGLE = 2  # Toggle relay.
    CYCLE_DELAY = 3  # Cycle the current state with a 30 second delay.


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
    relay_index: TruckerRelayIndex
    label: Optional[str]
    state: Optional[PinState] = PinState.OFF
    default_state: Optional[PinState] = PinState.OFF

    def __str__(self):
        return f'[{self.name}] {self.label} {self.state.name}'


class PowerBoard(PanBase):
    """Power distribution and monitoring.

    This represents a "trucker" board for PANOPTES, which is a combination of an
    Arduino Uno and an Infineon 24V relay shield.

    The relay shield has three PROFETs on them that are capable of sensing the
    current through the relay. RELAY_4 has a dedicated PROFET. The other two
    PROFETs can switch between two relays depending on the status of the appropriate
    DSEL pin.

    This class uses `panoptes.utils.device.serial.SerialDevice` for threaded (async)
    reading of the values from the Arduino Uno connected to the power board, which
    are parsed by the default callback and appended to a `deque` whose size can
    be controlled. A custom callback can be passed that should accept a single
    string parameter and return a dictionary.

    It also creates a `dataframe` attribute which is a
    `streamz.dataframe.PeriodicDataFrame` with a default call of
    `dataframe_period='50ms'`. If `None` then no dataframe is created.

    Pin names specified above correspond to Infineon terminology. See manual:
    https://bit.ly/2IGgWLQ.
    """

    def __init__(self,
                 port: str = None,
                 name: str = 'Power Board',
                 relays: Dict[str, dict] = None,
                 reader_callback: Callable[[dict], dict] = None,
                 dataframe_period: str = '50ms',
                 *args, **kwargs):
        """Initialize the power board.

        The `relays` should be a dictionary with the relay name as key and a
        dict with `label` and `initial_state` entries::

            RELAY_0:
                label: mount
                default_state: on

        Args:
            port (str, optional): The dev port for the arduino, if not provided, search for port
                matching the vendor (2341) and product id (0043).
            name (str): The user-friendly name for the power board.
            relays (dict[Relay] or None): The relay configuration. See notes for details.
        """
        super().__init__(*args, **kwargs)
        if port is None:
            port = PowerBoard.lookup_port(**kwargs)
            self.logger.info(f'Guessing that arduino is on {port=}')

        self.port = port
        self.name = name

        reader_callback = reader_callback or self.default_reader_callback

        self.logger.debug(f'Setting up Power board connection for {name=} on {self.port}')
        self._ignore_readings = 5
        self.arduino_board = SerialDevice(port=self.port,
                                          serial_settings=dict(baudrate=9600),
                                          reader_callback=reader_callback,
                                          )

        self.relays: List[Relay] = list()
        self.relay_labels: Dict[str, Relay] = dict()
        self.setup_relays(relays)
        time.sleep(2)

        # Set initial relay states.
        for relay in self.relays:
            self.logger.info(f'Setting {relay.label} to {relay.default_state.name}')
            self.change_relay_state(relay, TruckerBoardCommands(relay.default_state))

        self.dataframe = None
        if dataframe_period is not None:
            self.dataframe = PeriodicDataFrame(interval=dataframe_period, datafn=self.to_dataframe)
        self.logger.info(f'Power board initialized')

    def turn_on(self, label):
        """Turns on the relay with the given label."""
        self.change_relay_state(self.relay_labels[label], TruckerBoardCommands.ON)

    def turn_off(self, label):
        """Turns off the relay with the given label."""
        self.change_relay_state(self.relay_labels[label], TruckerBoardCommands.OFF)

    def toggle_relay(self, label):
        """Toggle relay from OFF<->ON"""
        self.change_relay_state(self.relay_labels[label], TruckerBoardCommands.TOGGLE)

    def cycle_relay(self, label):
        """Cycle the relay with a default 5 second delay."""
        self.change_relay_state(self.relay_labels[label], TruckerBoardCommands.CYCLE_DELAY)

    def to_dataframe(self, **kwargs):
        try:
            columns = ['time'] + list(self.relay_labels.keys())
            df0 = pd.DataFrame(self.arduino_board.readings, columns=columns)
            df0.set_index(['time'], inplace=True)
        except:
            df0 = pd.DataFrame([], index=pd.DatetimeIndex([]))

        return df0

    def setup_relays(self, relays: Dict[str, dict]):
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
                          default_state=default_state
                          )

            # Add convenience methods on the relay itself.
            relay.turn_on = partial(self.turn_on, relay.label)
            relay.turn_off = partial(self.turn_off, relay.label)

            # Track relays by list and by friendly label.
            self.relays.append(relay)
            self.relay_labels[relay.label] = relay

            # Set an attribute on the board for easy access by name and label.
            setattr(self, relay.name, relay)
            setattr(self, relay.label, relay)

            self.logger.info(f'{relay.label} added to board')

        self.logger.info(f'Relays: {self.relays!r}')

    def change_relay_state(self, relay: Relay, new_state_command: TruckerBoardCommands):
        """Changes the relay to the new state."""
        write_command = to_json(dict(relay=relay.relay_index.value, power=new_state_command.value))
        self.logger.debug(f'Sending relay state change command to board: {write_command!r}')
        self.arduino_board.write(f'{write_command}')

    def default_reader_callback(self, data):
        name_key = 'name'
        relay_key = 'relays'
        values_key = 'readings'

        if self._ignore_readings > 0:
            self._ignore_readings -= 1
            return

        self.logger.trace(f'Received: {data!r}')
        try:
            data = from_json(data)
        except error.InvalidDeserialization as e:
            self.logger.warning(f'Error here: {e!r}')
            return

        if data[name_key] != 'power_board':
            self.logger.warning('Not reading the power_board. Skipping data.')
            return

        # Check we got a valid reading.
        if len(data[relay_key]) != len(TruckerRelayIndex) \
                and len(data[values_key]) != len(TruckerRelayIndex):
            self.logger.debug('Did not get a full valid reading')
            return

        # Todo: make sure not receiving stale or out of order data using `uptime`.
        # Create a list for the new data row and add common time.
        new_data = [current_time().to_datetime()]
        for relay_index, read_relay in enumerate(self.relays):
            # Record the new value.
            new_data.append(data[values_key][relay_index])
            # Update the state of the pin.
            read_relay.state = PinState(data[relay_key][relay_index])

        return new_data

    def __str__(self):
        relay_states = ' '.join([POWER_SYMBOLS[r.state] for r in self.relays])
        return f'{self.name} [{relay_states}]'

    def __repr__(self):
        return to_json({
            'name': self.name,
            'port': self.port,
            'relays': [dict(name=r.name, label=r.label, state=r.state.name) for r in self.relays],
        })

    @classmethod
    def lookup_port(cls, vendor_id=0x2341, product_id=0x0043, **kwargs):
        """Tries to guess the port hosting the power board arduino.

        The default vendor_id is for official Arduino products. The default product_id
        is for an Uno Rev 3.

        https://github.com/arduino/Arduino/blob/1.8.0/hardware/arduino/avr/boards.txt#L51-L58

        """
        return find_serial_port(vendor_id, product_id)
