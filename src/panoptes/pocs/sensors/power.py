import time
from enum import IntEnum
from dataclasses import dataclass
from typing import Optional
from collections import deque

from panoptes.utils.serial.device import SerialDevice, find_serial_port
from panoptes.utils.serializers import to_json
from panoptes.pocs.base import PanBase


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
        return self.current_readings[-1]

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
            port = PowerBoard.lookup_port(**kwargs)
            self.logger.info(f'Guessing that arduino is on {port=}')

        self.port = port
        self.name = name

        self.logger.debug(f'Setting up Power board connection for {name=} on {self.port}')
        self.arduino_board = SerialDevice(port=self.port,
                                          serial_settings=dict(baudrate=9600)
                                          )
        self.alive = False

        self.relay_labels = dict()
        self.relay_names = dict()
        self.setup_relays(relays, queue_maxsize=25)
        time.sleep(2)

        # Set initial relay states.
        for relay in self.relay_names.values():
            self.logger.info(f'Setting {relay.label} to {relay.default_state.name}')
            self.change_relay_state(relay, relay.default_state)

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

            current_deque = deque(maxlen=queue_maxsize)

            # Create relay object.
            self.logger.debug(f'Creating {relay_label=} for {relay_config!r}')
            relay = Relay(name=relay_name,
                          label=relay_config.get('label', ''),
                          relay_index=relay_index,
                          current_readings=current_deque,
                          default_state=default_state
                          )

            # Track relays by name and friendly label.
            self.relay_names[relay.name] = relay
            self.relay_labels[relay.label] = relay

            # Set an attribute on the board for easy access by name and label.
            setattr(self, relay.name, relay)
            setattr(self, relay.label, relay)

            self.logger.info(f'{relay.label} added to board')

        self.logger.success(f'Relays: {self.relay_names!r}')

    def change_relay_state(self, relay: Relay, new_state: PinState):
        """Changes the relay to the new state. """
        new_state_command = TruckerBoardCommands[new_state.name]
        # Must have the newline in command.
        write_command = to_json(dict(relay=relay.relay_index.value, power=new_state_command.value))
        self.logger.debug(f'Sending relay state change command to board: {write_command!r}')
        self.arduino_board.write(f'{write_command}')

    def __str__(self):
        relay_states = ' '.join([f'{r.name}: {r.state.name}' for r in self.relay_names.values()])
        return f'{self.name} - {relay_states}'

    @classmethod
    def lookup_port(cls, vendor_id=0x2341, product_id=0x0043, **kwargs):
        """Tries to guess the port hosting the power board arduino.

        The default vendor_id is for official Arduino products. The default product_id
        is for an Uno Rev 3.

        https://github.com/arduino/Arduino/blob/1.8.0/hardware/arduino/avr/boards.txt#L51-L58

        """
        return find_serial_port(vendor_id, product_id)
