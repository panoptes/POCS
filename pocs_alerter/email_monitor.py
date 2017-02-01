#!/usr/bin/env python

from email_parser import ParseEmail
import argparse
import time

parser = argparse.ArgumentParser()

parser.add_argument('-host', default='imap.gmail.com', dest='host', type=str,
                    help='The email server host. Use default for gmail.')
parser.add_argument('-email', dest='email', type=str, help='The email address. Required.',
                    required=True)
parser.add_argument('-password', dest='password', type=str, help='The password. Required.',
                    required=True)
parser.add_argument('-test', default=False, dest='test', type=bool, help='Turns on testing.')
parser.add_argument('-rescan', default=2.0, dest='rescan', type=float,
                    help='Sets the frequency of email checks. Must be given in minutes.')
parser.add_argument('-grav_wave_selection', default={'name': 'observable_tonight', 'max_tiles': 100},
                    dest='grav_wave_selection', help='Selection criteria for the gravity wave \n \
                     tiling algorithm. Must be a python dictionary, with a name and max_tiles. \n \
                     If desired to tile sky observable tonight, set name to "observable_tonight".')


def loop_over_time(email_monitor, rescan_interval):

    while True:

        try:

            for typ in types_noticed:

                read, text = email_monitor.get_email(typ, folder='inbox')

                if read:

                    message = email_monitor.read_email(text)

                    email_monitor.parse_event(message)

            time.sleep(rescan_interval * 60)

        except KeyboardInterrupt:

            break


if __name__ == '__main__':

    args = parser.parse_args()

    email_monitor = ParseEmail(args.host, args.email, args.password, test=args.test,
                               rescan_interval=args.rescan, selection_criteria=args.grav_wave_selection)

    loop_over_time(email_monitor, args.rescan_interval)
