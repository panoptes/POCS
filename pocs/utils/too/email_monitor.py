#!/usr/bin/env python

from pocs.utils.too.email_parser import email_parser
from pocs.utils.config import load_config
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
parser.add_argument('--config', default='local_config', dest='config', help='The \
                    local config file containing information about the Field of Vew and the selection_criteria')
parser.add_argument('--alert_pocs', default=True, dest='alert_pocs', help='Tells the code whether or not to alert \
                    POCS with found targets')
parser.add_argument('--selection_criteria', default='', dest='selection_criteria',
                    help='The python dictionary containint our selection criteria')


def loop_each_monitor(email_monitor, rescan_interval, types_noticed):

    targets = []
    print('For monitor: ', str(email_monitor))
    for typ in types_noticed:
        print('Reading email: ', typ)
        read, text = email_monitor.get_email(typ)

        if read:
            targets = email_monitor.parse_event(text)

    time.sleep(rescan_interval * 60)
    return targets


def loop_over_time(email_monitors, rescan_interval):

    while True:

        try:

            for email_monitor in email_monitors:

                targets = loop_each_monitor(email_monitor[0], rescan_interval, email_monitor[1])

        except KeyboardInterrupt:

            break


def create_monitors(config_file, host, email, password, alert_pocs, selection_criteria, test):

    config = load_config(config_file)

    parser_list = []

    for parser_info in config['email_parsers']:
        try:
            module = getattr(email_parser, parser_info['type'])
            params = parser_info['inputs']

            parser = module(
                host,
                email,
                password,
                alert_pocs=alert_pocs,
                configname=config_file,
                selection_criteria=selection_criteria,
                test=test)
            parser_list.append([parser, parser_info['subjects']])

        except Exception as e:
            print("Can't create parser. Error: ", e)
            raise e

    return parser_list


if __name__ == '__main__':

    args = parser.parse_args()

    email_monitors = create_monitors(
        args.config,
        args.host,
        args.email,
        args.password,
        args.alert_pocs,
        args.selection_criteria,
        args.test)

    loop_over_time(email_monitors, args.rescan_interval)
