from abc import ABC, abstractmethod

from panoptes.utils.config.client import get_config

from ...utils.logger import get_logger

from .relay import Relay

logger = get_logger()


class PowerBoard(ABC):
    def __init__(self, board_config=None):
        """Set up a power relay and distribution board.

        The base board itself provides very little functionality and serves mostly
        as a holder for the relays.

        A `panoptes.pocs.sensors.power.Relay` should be capable of turning itself
        on and off and optionally provide current sensing.

        Args:
            board_config (dict or None): The configuration for the power relay
                board. If `None` is provided, query the config server. Default
                `None.`
        """
        self.board_config = board_config or get_config('environment.power_board')
        assert isinstance(self.board_config, dict)

        self.name = self.board_config.get('name', 'Generic PowerBoard')

        self.relays = list()
        self._initialize_relays()

        self.success(f'{self.name} initialized')


    def _initialize_relays(self):
        logger.info(f'Setting up relays for {self}')
        relays = self.board_config.get('relays', list())

        for i, relay_config in enumerate(relays):
            relay = Relay(**relay_config)
            self.info(f'Created relay {i:02d}: {relay=}')


    def __str__(self):
        return f'{self.name}: {self.relays}'

