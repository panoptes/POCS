# Note: list_comports is modified by test_sensors.py, so if changing
# this import, the test will also need to be updated.
from serial.tools.list_ports import comports as list_comports

from panoptes.pocs.utils.logger import get_logger
from panoptes.utils.rs232 import SerialData

logger = get_logger()


def find_arduino_devices(com_ports=None):
    """Find devices (paths or URLs) that appear to be Arduinos.

    Returns:
        list of str: device paths (e.g. ``/dev/ttyACM1``) or URLs (e.g.
            ``rfc2217://host:port``, ``arduino_simulator://?board=camera``).
    """
    com_ports = com_ports or list_comports()
    logger.debug(f'Looking for arduinos in {com_ports=}')
    arduinos = [p.device for p in com_ports if 'Arduino' in p.description]
    logger.info(f'Auto-detected {arduinos=}')
    boards = {port: detect_board_on_port(port) for port in arduinos}
    logger.info(f'Found {boards=}')
    return boards


def detect_board_on_port(port):
    """Open a port and determine try to determine board type from name.

    Returns:
        str or None: The ``name`` value as read from the board, otherwise ``None``.
    """
    logger.debug(f'Attempting to connect to serial port: {port=}')

    try:
        serial_reader = SerialData(port=port,
                                   baudrate=9600,
                                   retry_limit=1,
                                   retry_delay=0,
                                   )
        if not serial_reader.is_connected:
            serial_reader.connect()
        logger.debug(f'Connected to {port=}')
    except Exception as e:
        logger.warning(f'Could not connect to {port=}: {e}')

    try:
        ts, data = serial_reader.get_and_parse_reading(retry_limit=3)
        name = data.get('name', None)
        if name is None:
            logger.info(f'Unable to find board name in reading: {data!r}')
    except Exception as e:
        logger.error(f'Exception while auto-detecting {port=}: {e!r}')

    serial_reader.disconnect()

    return name
