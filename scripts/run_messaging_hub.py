#!/usr/bin/env python3

import argparse
import sys
import threading
import time

from pocs.utils.config import load_config
from pocs.utils.logger import get_root_logger
from pocs.utils.messaging import PanMessaging

the_root_logger = None


def say(fmt, *args, error=False):
    if args:
        msg = fmt.format(*args)
    else:
        msg = fmt
    if error:
        print(msg, file=sys.stderr)
        the_root_logger.error(msg)
    else:
        print(msg)
        the_root_logger.info(msg)


def run_forwarder(sub_port, pub_port, sub, pub):
    try:
        PanMessaging.run_forwarder(sub, pub)
    finally:
        say('Forwarder for {} -> {} has stopped', sub_port, pub_port)


def run_forwarders(port_pairs):
    the_root_logger.info('Creating sockets')

    socket_pairs = []
    for sub, pub in port_pairs:
        say('Creating sockets for {} -> {}', sub, pub)
        try:
            socket_pairs.append(PanMessaging.create_forwarder_sockets(sub, pub))
        except Exception as e:
            say('Unable to create sockets: {}', e, error=True)
            sys.exit(1)

    say('Starting forwarders')

    threads = []
    for ports, sockets in zip(port_pairs, socket_pairs):
        sub_port, pub_port = ports
        name = 'fwd_{}_to_{}'.format(sub_port, pub_port)
        sub, pub = sockets
        t = threading.Thread(
            target=run_forwarder, name=name, args=(sub_port, pub_port, sub, pub), daemon=True)
        the_root_logger.info('Starting thread {}', name)
        t.start()
        threads.append(t)

    time.sleep(0.05)
    if not any([t.is_alive() for t in threads]):
        say('Failed to start any forwarder!', error=True)
        sys.exit(1)
    else:
        the_root_logger.info('Started all forwarders')
        print()
        print('Hit Ctrl-c to stop')
    try:
        # Keep running until they've all died.
        while threads:
            for t in threads:
                t.join(timeout=100)
                if t.is_alive():
                    continue
                say('Thread {} has stopped', t.name, error=True)
                threads.remove(t)
                break
        # If we get here, then the forwarders died for some reason.
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Run one or more zeromq message forwarder(s).')
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

    def arg_error(msg):
        print(msg, file=sys.stderr)
        parser.print_help()
        sys.exit(1)

    all_ports = []

    def validate_unique_port(port):
        """Confirm that the port is valid and unique among all the ports."""
        if not (1024 < port and port < 65536):
            arg_error(
                'Port {} is unsupported; must be between 1024 and 65536, exclusive.'.format(port))
        if port in all_ports:
            arg_error('Port {} specified more than once.'.format(port))
        all_ports.append(port)

    sub_and_pub_pairs = []

    def add_pair(sub, pub=None):
        validate_unique_port(sub)
        if pub is None:
            pub = sub + 1
        elif sub == pub:
            arg_error('Port pair {} -> {} invalid. Ports must be distinct.'.format(sub, pub))
        validate_unique_port(pub)
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

    if not sub_and_pub_pairs:
        arg_error('Found no port pairs to forward between.')

    the_root_logger = get_root_logger()

    run_forwarders(sub_and_pub_pairs)
