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
        
        if 'social_accounts' in config:
            social_config = config['social_accounts']

            # See which social sink we can create based on config

            # Twitter sink
            if social_config is not None and 'twitter' in social_config:
                twitter_config = social_config['twitter']
                if twitter_config is not None and \
                        'consumer_key' in twitter_config and \
                        'consumer_secret' in twitter_config and \
                        'access_token' in twitter_config and \
                        'access_token_secret' in twitter_config:
                    # Output timestamp should always be True in Twitter
                    # otherwise Twitter will reject duplicate statuses
                    if 'output_timestamp' in twitter_config:
                        output_timestamp = twitter_config['output_timestamp']
                    else:
                        output_timestamp = True

                    social_twitter = SocialTwitter(twitter_config['consumer_key'],
                                                    twitter_config['consumer_secret'],
                                                    twitter_config['access_token'],
                                                    twitter_config['access_token_secret'],
                                                    output_timestamp)

            # Slack sink
            if social_config is not None and 'slack' in social_config:
                slack_config = social_config['slack']
                if slack_config is not None and \
                        'webhook_url' in slack_config:

                    if 'output_timestamp' in slack_config:
                        output_timestamp = slack_config['output_timestamp']
                    else:
                        output_timestamp = False

                    social_slack = SocialSlack(slack_config['webhook_url'],
                                                    output_timestamp)
        else:
            arg_error('social_accounts setting not defined in config.')

    if not social_twitter and not social_slack:
        arg_error('No social messaging sinks could be initialised. Please check your config settings.')

    # Messaging port to subscribe on
    msg_port = config['messaging']['msg_port'] + 1

    the_root_logger = get_root_logger()

    run_social_sinks(msg_port, social_twitter, social_slack)
