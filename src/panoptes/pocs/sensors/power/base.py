from abc import ABC, abstractmethod

from panoptes.utils.config.client import get_config

from ...utils.logger import get_logger

from .relay import Relay

logger = get_logger()


class PowerBoard(ABC):
    relays = list()
    board_config = dict()

    def __init__(self, board_config=None):
        """Set up a power relay and distribution board.

        Args:
            board_config (dict or None): The configuration for the power relay
                board. If `None` is provided, query the config server. Default
                `None.`
        """
        self.board = None
        self.relays = list()
        self.board_config = board_config or get_config('environment.power_board')

        logger.info(f'Setting up relays for {self}')
        self.setup_relays()

    def setup_relays(self):
        # Setup relays
        for port, pin in self.board_config['pin_mapping'].items():
            relay_name = self.board_config['ports'][port]
            initial_state = self.board_config['initial_state'][port]

            logger.debug(f'Setting up {port=} for {relay_name=} with {initial_state=} on {pin=}')
            relay = Relay(relay_name, pin)

            if initial_state == 'on':
                relay.turn_on()

            self.relays.append(relay)

    def __str__(self):
        return f'Power board: {self.relays}'
