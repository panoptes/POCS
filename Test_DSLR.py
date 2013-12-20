#!/usr/env/python

# from __future__ import division, print_function

## Import General Tools
import sys
import os
import argparse
import logging

import serial

##-------------------------------------------------------------------------
## Main Program
##-------------------------------------------------------------------------
def main():

    ##-------------------------------------------------------------------------
    ## Parse Command Line Arguments
    ##-------------------------------------------------------------------------
    ## create a parser object for understanding command-line arguments
    parser = argparse.ArgumentParser(
             description="Program description.")
    ## add flags
    parser.add_argument("-v", "--verbose",
        action="store_true", dest="verbose",
        default=False, help="Be verbose! (default = False)")
    ## add arguments
    parser.add_argument("--command", "-c",
        type=str, dest="command",
        help="Command string to send to Arduino.")
    args = parser.parse_args()

    ##-------------------------------------------------------------------------
    ## Create logger object
    ##-------------------------------------------------------------------------
    logger = logging.getLogger('MyLogger')
    logger.setLevel(logging.DEBUG)
    ## Set up console output
    LogConsoleHandler = logging.StreamHandler()
    if args.verbose:
        LogConsoleHandler.setLevel(logging.DEBUG)
    else:
        LogConsoleHandler.setLevel(logging.INFO)
    LogFormat = logging.Formatter('%(asctime)23s %(levelname)8s: %(message)s')
    LogConsoleHandler.setFormatter(LogFormat)
    logger.addHandler(LogConsoleHandler)
    ## Set up file output
#     LogFileName = None
#     LogFileHandler = logging.FileHandler(LogFileName)
#     LogFileHandler.setLevel(logging.DEBUG)
#     LogFileHandler.setFormatter(LogFormat)
#     logger.addHandler(LogFileHandler)


    ##-------------------------------------------------------------------------
    ## Send command over serial
    ##-------------------------------------------------------------------------
    connection = serial.Serial('/dev/tty.usbmodemfd1251', 9600, timeout=3.5)
    send_string = str(args.command + '/n')
    connection.write(send_string)
    response = connection.readline()
    if response != '':
        print(response)
    else:
        print("No response from Arduino.")
    connection.close()




if __name__ == '__main__':
    main()
