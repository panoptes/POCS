#!/usr/bin/env python

from email_parser import ParseEmail
import argparse

parser = argparse.ArgumentParser()

parser.add_argument('-host', default = 'imap.gmail.com', dest = 'host', type = str,
                    help = 'The email server host. Use default for gmail.')
parser.add_argument('-email', dest = 'email', type = str, help = 'The email address. Required.',
                     required = True)
parser.add_argument('-password', dest = 'password', type = str, help = 'The password. Required.',
                     required = True)
parser.add_argument('-test', default = False, dest = 'test', type = bool, help = 'Turns on testing.')
parser.add_argument('-rescan', default = 2.0, dest = 'rescan', type = float,
                     help = 'Sets the frequency of email checks. Must be given in minutes.')
parser.add_argument('-loop_until', default = 'tonight', dest = 'loop_until', type = str,
                     help = 'The time for this script to run.')
parser.add_argument('-until', default = '', dest = 'until', help = 'Time until script runs. \n \
                    -loop_until must be set to "until" and value must be time object.')
parser.add_argument('-grav_wave_selection', default = {'name': 'observable_tonight', 'max_tiles': 100},
                     dest = 'grav_wave_selection', help = 'Selection criteria for the gravity wave \n \
                     tiling algorithm. Must be a python dictionary, with a name and max_tiles. \n \
                     If desired to tile sky observable tonight, set name to "observable_tonight".')

if __name__ == '__main__':

    args = parser.parse_args()

    email_monitor = PraseEmail(args.host, args.email, args.password, test = args.test,
                               rescan_interval = args.rescan, criteria_for_loop = args.loop_until,
                               until = args.until, selection_criteria = args.grav_wave_selection)

    email_monitor.loop_over_time()