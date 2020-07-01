from pymata_express import pymata_express

from ...utils.logger import get_logger

from .base import PowerBoard

logger = get_logger()


class FirmataPowerBoard(PowerBoard):
    """Represents a power relay board.

    A `PowerBoard` consists of any number of `panoptes.pocs.sensors.Relays` that
    can be switched (on/off) and which supports current monitoring.

    """

    def __init__(self, board_config=None):
        """Initialize the power board.

        Gets pins and relays into initial state.
        """
        logger.debug(f'Setting up firmata-based power board with {self.board_config=}')
        super().__init__(board_config=board_config)

        self.board = pymata_express.PymataExpress()

    def __str__(self):
        return f'Firmata power board: {self.relays}'
