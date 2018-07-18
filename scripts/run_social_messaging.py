#!/usr/bin/env python

import argparse
import sys
import threading
import time
import zmq

from pocs.utils.config import load_config
from pocs.utils.logger import get_root_logger
from pocs.utils.messaging import PanMessaging
from pocs.utils.social_twitter import SocialTwitter
from pocs.utils.social_slack import SocialSlack

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


def check_social_messages_loop(msg_port, social_twitter, social_slack):
    cmd_social_subscriber = PanMessaging.create_subscriber(msg_port, 'PANCHAT')

    poller = zmq.Poller()
    poller.register(cmd_social_subscriber.socket, zmq.POLLIN)

    try:
        while True:
            # Poll for messages
            sockets = dict(poller.poll(500))  # 500 ms timeout

            if cmd_social_subscriber.socket in sockets and \
                    sockets[cmd_social_subscriber.socket] == zmq.POLLIN:

                msg_type, msg_obj = cmd_social_subscriber.receive_message(flags=zmq.NOBLOCK)

                # Check the various social sinks
                if social_twitter is not None:
                    social_twitter.send_message(msg_obj['message'], msg_obj['timestamp'])

                if social_slack is not None:
                    social_slack.send_message(msg_obj['message'], msg_obj['timestamp'])

            time.sleep(1)
    except KeyboardInterrupt:
        pass


def run_social_sinks(msg_port, social_twitter, social_slack):
    the_root_logger.info('Creating sockets')

    threads = []
    
    name='social_messaging'

    t = threading.Thread(
            target=check_social_messages_loop, name=name, args=(msg_port, social_twitter, social_slack), daemon=True)
    the_root_logger.info('Starting thread {}', name)
    t.start()
    threads.append(t)

    time.sleep(0.05)
    if not any([t.is_alive() for t in threads]):
        say('Failed to start social sinks thread!', error=True)
        sys.exit(1)
    else:
        the_root_logger.info('Started social messaging')
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
        description='Run social messaging to forward platform messages to social channels.')
    parser.add_argument(
        '--from_config',
        action='store_true',
        help='Read social channels config from the pocs.yaml and pocs_local.yaml config files.')
    args = parser.parse_args()

    def arg_error(msg):
        print(msg, file=sys.stderr)
        parser.print_help()
        sys.exit(1)

    # Initialise social sinks to None
    social_twitter = None
    social_slack = None
    
    if args.from_config:
        config = load_config(config_files=['pocs'])

        social_config = config.get('social_accounts')
        if social_config:
            # Check which social sinks we can create based on config

            # Twitter sink
            twitter_config = social_config.get('twitter')
            if twitter_config:
                try:
                    social_twitter = SocialTwitter(**twitter_config)
                except ValueError as e:
                    print('Twitter sink could not be initialised. Please check your config. Error: {}'.format(str(e)))

            # Slack sink
            slack_config = social_config.get('slack')
            if slack_config:
                try:
                    social_slack = SocialSlack(**slack_config)
                except ValueError as e:
                    print('Slack sink could not be initialised. Please check your config. Error: {}'.format(str(e)))
        else:
            print('No social accounts defined in config, exiting.')
            sys.exit(0)

    if not social_twitter and not social_slack:
        print('No social messaging sinks defined, exiting.')
        sys.exit(0)

    # Messaging port to subscribe on
    msg_port = config['messaging']['msg_port'] + 1

    the_root_logger = get_root_logger()

    run_social_sinks(msg_port, social_twitter, social_slack)
