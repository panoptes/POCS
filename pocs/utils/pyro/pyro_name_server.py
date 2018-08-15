#!/usr/bin/env python
import argparse
import os
from Pyro4 import naming, errors, config

from pocs.utils.pyro import get_own_ip


def run_name_server(host=None, port=None, autoclean=0):
    try:
        # Check that there isn't a name server already running
        name_server = naming.locateNS()
    except errors.NamingError:
        if not host:
            # Not given an hostname or IP address. Will attempt to work it out.
            host = get_own_ip(verbose=True)
        else:
            host = str(host)

        if port:
            port = int(port)
        else:
            port = None

        config.NS_AUTOCLEAN = float(autoclean)

        print("Starting Pyro name server... (Control-C/Command-C to exit)")
        naming.startNSloop(host=host, port=port)
    else:
        print("Pyro name server {} already running! Exiting...".format(name_server))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", help="hostname or IP address to bind the server on")
    parser.add_argument("--port", help="port number to bind the server on")
    parser.add_argument("--autoclean", help="interval between registration autoclean (0=disabled)",
                        default=30)
    args = parser.parse_args()
    run_name_server(args.host, args.port, args.autoclean)
