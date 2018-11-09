# This script is used by peas_shell to record the readings from an
# Arduino, and to send commands to the Arduino (e.g. to open and
# close relays).

import argparse
import serial
import sys

from pocs.sensors import arduino_io
from pocs.utils import DelaySigTerm
from pocs.utils.config import load_config
from pocs.utils.database import PanDB
from pocs.utils.logger import get_root_logger
from pocs.utils.messaging import PanMessaging


def main(board, port, cmd_port, msg_port, db_type, db_name):
    config = load_config(config_files=['peas'])
    serial_config = config.get('environment', {}).get('serial', {})
    logger = get_root_logger()
    serial_data = arduino_io.open_serial_device(port, serial_config=serial_config, name=board)
    db = PanDB(db_type=db_type, db_name=db_name, logger=logger).db
    sub = PanMessaging.create_subscriber(cmd_port)
    pub = PanMessaging.create_publisher(msg_port)
    aio = arduino_io.ArduinoIO(board, serial_data, db, pub, sub)
    def request_to_stop_running(**kwargs):
        aio.stop_running = True
    with DelaySigTerm(callback=request_to_stop_running):
        aio.run()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Record sensor data from an Arduino and send it relay commands.')
    parser.add_argument(
        '--board', required=True,
        help="Name of the board attached to the port. Currently: 'camera' or 'telemetry'")
    parser.add_argument('--port', help='Port (device path) to connect to.')
    parser.add_argument(
        '--simulate',
        action='store_true',
        help='Simulate the named board instead of connecting to a real serial port.')
    parser.add_argument(
        '--cmd-sub-port',
        dest='cmd_port',
        default=6501,
        help='Port (e.g. 6501) on which to listen for commands.')
    parser.add_argument(
        '--msg-pub-port',
        dest='msg_port',
        default=6510,
        help='Port (e.g. 6510) to which to publish readings.')
    parser.add_argument(
        '--db-type', dest='db_type', default='file', help='Database type (mongo or file).')
    parser.add_argument('--db-name', dest='db_name', default='panoptes', help='Database name.')
    args = parser.parse_args()

    def arg_error(msg):
        print(msg, file=sys.stderr)
        parser.print_help()
        sys.exit(1)

    if args.board in ('camera', 'camera_board'):
        board = 'camera_board'
    elif args.board in ('telemetry', 'telemetry_board'):
        board = 'telemetry_board'
    else:
        arg_error("--board must be 'camera', 'camera_board', 'telemetry' or 'telemetry_board'")

    if args.port and not args.simulate:
        port = args.port
    elif args.simulate and not args.port:
        serial.protocol_handler_packages.insert(0, 'pocs.serial_handlers')
        port = 'arduinosimulator://?board=' + board.replace('_board', '')
    else:
        arg_error('Must specify exactly one of --port or --simulate')

    if not args.cmd_port or not args.msg_port:
        arg_error('Must specify both --cmd-port and --msg-port')

    if not args.db_type or not args.db_name:
        arg_error('Must specify both --db-type and --db-name')

    print('args: {!r}'.format(args))
    print('board:', board)
    print('port:', port)

    # To provide distinct log file names for each board, change argv
    # so that the board name is used as the invocation name. This may not
    # work if the logger has already been started.
    sys.argv[0] = board

    main(board, port, args.cmd_port, args.msg_port, args.db_type, args.db_name)
