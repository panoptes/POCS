#!/usr/bin/env python

import argparse
import time

from pocs.utils.config import load_config
from pocs.utils.too.email_parser import email_parser
from warnings import warn

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
parser.add_argument('--config', default='email_parsers', dest='config', help='The \
                    local config file containing information about the Field of Vew and the selection_criteria')
parser.add_argument('--alert_pocs', default=True, dest='alert_pocs', help='Tells the code whether or not to alert \
                    POCS with found targets')
parser.add_argument('--selection_criteria', default=None, dest='selection_criteria',
                    help='The python dictionary containint our selection criteria')
parser.add_argument('--verbose', default=False, dest='verbose',
                    help='Activates print statements.')
parser.add_argument('--archive', default=True, dest='archive', help='Tells the parsers to archive mail they read.')


def read_email_in_monitor(email_monitor, types_noticed):
    '''For an email monitor, it loops over relevat subject names and attempts to read
    email with those subjects.

    Args:
        - monitor (EmailParser): the email monitor attempting to read emails.
        - types_notices (list of strings): the subjects which the monitor will attempt to read.

    Returns:
        - the list of targets as python dictionaries.
        - exit_after (bool): command to either keep looping or exit the monitor.'''

    targets = []
    print('For monitor: ', str(email_monitor))
    for email_type in types_noticed:
        print('Reading email: ', email_type)
        read, text, exit_after = email_monitor.get_email(email_type)

        if read:
            targets = email_monitor.parse_event(text)

    return targets, exit_after


def create_monitors(config_file, host, email, password, alert_pocs, selection_criteria, test, verbose, archive):
    '''Creates a list of eail email_monitor by reading the relevant config file.

    Args:
        - config_file (str): anme of config file to read.
        - host (str): email host name.
        - email (str): email address.
        - password (str): email password
        - alert_pocs (bool): tells the parser whether or not
            to send an alert with the targets.
        - selection_criteria (dictionary): used for gravity wave email parser.
        - test (bool): enables the reading of test event emails.
        - verbose (bool): enables printing statements in all methods.
        - archive (bool): if True, the parsers try to archive mail they read. If they fail,
            or if False, the monitor will exit.

    Returns:
        - list of Email parser objects. Raises error if any parser cannot be created.'''

    config = load_config(config_file)

    parser_list = []

    for parser_info in config['email_parsers']:
        try:
            module = getattr(email_parser, parser_info['type'])

            parser = module(
                host,
                email,
                password,
                alert_pocs=alert_pocs,
                configname=config_file,
                selection_criteria=selection_criteria,
                test_message=test,
                verbose=verbose,
                move_to_archive=archive)
            parser_list.append([parser, parser_info['subjects']])

        except Exception as e:
            warn("Can't create parser!")
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
        args.test,
        args.verbose,
        args.archive)

    exit_after = False

    while not exit_after:

        try:

            for email_monitor in email_monitors:

                targets, exit_after = read_email_in_monitor(email_monitor[0], email_monitor[1])

            time.sleep(args.rescan * 60)

        except KeyboardInterrupt:

            break
