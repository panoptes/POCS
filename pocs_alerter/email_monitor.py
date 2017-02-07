#!/usr/bin/env python

from pocs_alerter.email_parser import email_parser
import argparse
import time
import yaml

parser = argparse.ArgumentParser()

parser.add_argument('--host', default='imap.gmail.com', dest='host', type=str,
                    help='The email server host. Use default for gmail.')
parser.add_argument('--email', dest='email', type=str, help='The email address. Required.',
                    required=True)
parser.add_argument('--password', dest='password', type=str, help='The password. Required.',
                    required=True)
parser.add_argument('--test', default=False, dest='test', type=bool, help='Turns on testing.')
parser.add_argument('--rescan', default=2.0, dest='rescan', type=float,
                    help='Sets the frequency of email checks. Must be given in minutes.')
parser.add_argument('--subjects', default=['GCN/LVC_INITIAL', 'GCN/LVC_UPDATE'], dest='subjects',
                    help='The email subjects which we want to read. Must be a python list containing \n\
                    strings which exactly match the email subjects.')
parser.add_argument('--config', default='$POCS/local_config.yaml', dest='filename', help='The \
                    local config file containing information about the Field of Vew and the selection_criteria')
parser.add_argument('--alert_pocs', default=True, dest='alert_pocs', help='Tells the code whether or not to alert \
                    POCS with found targets')


def loop_each_monitor(email_monitor, rescan_interval, types_noticed):

    for typ in types_noticed:

        read, text = email_monitor.get_email(typ, folder='inbox')

        if read:
            message = email_monitor.read_email(text)
            email_monitor.parse_event(message)

    time.sleep(rescan_interval * 60)


def loop_over_time(email_monitors, rescan_interval, types_noticed, test):

    if test is True:
        types_notices.append('GCN/LVC_TEST')

    while True:

        try:

            for email_monitor in email_monitors:

                loop_each_monitor(email_monitor, rescan_interval, types_noticed)

        except KeyboardInterrupt:

            break


def load_config(filename):

    with open(filename, 'r') as f:

        config = yaml.load(f.read())

    return config


def create_monitors(config, host, email, password, alert_pocs):

    parser_list = []

    for parser_info in config['email_parsers']:
        try:
            module = getattr(email_parser, parser_info['type'])
            params = parser_info['inputs']

            parser = module(host, email, password, alert_pocs, **params)
            parser_list.append(parser)

        except Exception as e:
            print("Can't create parser ", e)
            raise e

    return parser_list

if __name__ == '__main__':

    args = parser.parse_args()
    config = load_config(args.filename)

    email_monitors = create_monitors(config, args.host, args.email, args.password, args.alert_pocs)

    loop_over_time(email_monitors, args.rescan_interval, args.types_notices, args.test)
