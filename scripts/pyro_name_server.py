#!/usr/bin/env python
import argparse
import os
from Pyro4 import naming, errors, config

from pocs.utils.pyro import get_own_ip

parser = argparse.ArgumentParser()
parser.add_argument("--host", help="hostname or IP address to bind the server on")
parser.add_argument("--port", help="port number to bind the server on")
parser.add_argument("--autoclean", help="interval between autoclean of registrations (0=disabled)",
                    default=0)
args = parser.parse_args()

try:
    # Check that there isn't a name server already running
    name_server = naming.locateNS()
except errors.NamingError:
    if not args.host:
        # Not given an hostname or IP address. Will attempt to work it out.
        host = get_own_ip(verbose=True)
    else:
        host = str(args.host)

    if args.port:
        port = int(args.port)
    else:
        port = None

    config.NS_AUTOCLEAN = float(args.autoclean)

    print("Starting Pyro name server... (Control-C/Command-C to exit)")
    naming.startNSloop(host=host, port=port)
else:
    print("Pyro name server {} already running! Exiting...".format(name_server))
