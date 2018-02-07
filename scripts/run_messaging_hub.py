#!/usr/bin/env python

import argparse
# import multiprocessing
import sys
import threading
import time

from pocs.utils.config import load_config
from pocs.utils.logger import get_root_logger
from pocs.utils.messaging import PanMessaging


def run_forwarder(logger, sub_port, pub_port):
    msg = 'Starting {} -> {} forwarder'.format(sub_port, pub_port)
    print(msg)
    logger.info(msg)
    try:
        PanMessaging.create_forwarder(sub_port, pub_port)
    except Exception:
        pass
    msg = 'Forwarder for {} -> {} has stopped'.format(sub_port, pub_port)
    print(msg)
    logger.info(msg)


def run_forwarders(sub_and_pub_pairs):
    logger = get_root_logger()
    logger.info('Starting forwarders')
    threads = []
    for sub, pub in sub_and_pub_pairs:
        name = 'fwd_{}_to_{}'.format(sub, pub)
        t = threading.Thread(target=run_forwarder, name=name, args=(logger, sub, pub), daemon=True)
        logger.info('Starting thread {}', name)
        t.start()
        threads.append(t)
        time.sleep(0.05)
    time.sleep(0.2)
    if not any([t.is_alive() for t in threads]):
        msg = 'Failed to start any forwarder!'
        logger.error(msg)
        print(msg)
    else:
        print()
        print('Hit Ctrl-c to stop')
    try:
        # Keep running until they've all died.
        while threads:
            for t in threads:
                t.join(timeout=100)
                if t.is_alive():
                    continue
                logger.info('Thread {} has stopped', t.name)
                threads.remove(t)
                break
        # If we get here, then the forwarders died for some reason.
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Record sensor data from an Arduino and send it relay commands.')
    parser.add_argument(
        '--pair',
        dest='pairs',
        nargs=2,
        action='append',
        type=int,
        help="Pair of ports to be forwarded: subscriber (input) port and publisher (output) port.")
    parser.add_argument(
        '--port',
        dest='ports',
        action='append',
        type=int,
        help='First port of a pair to be forwarded. The other is the next integer.')
    parser.add_argument(
        '--from_config',
        action='store_true',
        help='Read ports from the pocs.yaml and pocs_local.yaml config files.')
    args = parser.parse_args()
    print('args: {!r}'.format(args))

    def arg_error(msg):
        print(msg, file=sys.stderr)
        parser.print_help()
        sys.exit(1)

    all_ports = []

    def validate_port(port):
        if not (0 < port and port < 65536):
            arg_error(
                'Port {} is unsupported; must be between 0 and 65536, exclusive.'.format(port))
        if port in all_ports:
            arg_error('Port {} specified more than once.'.format(port))
        all_ports.append(port)

    sub_and_pub_pairs = []

    def add_pair(sub, pub=None):
        if pub is None:
            pub = sub + 1
        validate_port(sub)
        if sub == pub:
            arg_error('Port pair {} -> {} invalid. Ports must be distinct.'.format(sub, pub))
        validate_port(pub)
        all_ports.append(pub)
        sub_and_pub_pairs.append((sub, pub))

    if args.from_config:
        config = load_config(config_files=['pocs'])
        add_pair(config['messaging']['cmd_port'])
        add_pair(config['messaging']['msg_port'])

    if args.pairs:
        for sub, pub in args.pairs:
            add_pair(sub, pub)

    if args.ports:
        for sub in args.ports:
            add_pair(sub)

    print('pairs: {!r}'.format(sub_and_pub_pairs))

    if not sub_and_pub_pairs:
        arg_error('Found no port pairs to forward between.')

    run_forwarders(sub_and_pub_pairs)
