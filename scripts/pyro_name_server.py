#!/usr/bin/env python
"""
Script to run the Pyro name server. This must be running in order to use distributed cameras with
POCS. The name server can be run on any computer on the network, but would normally be run on the
main control computer. The name server should be started before the distributed camera servers and
POCS.
"""
import argparse

from pocs.utils.pyro import run_name_server

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", help="hostname or IP address to bind the server on")
    parser.add_argument("--port", help="port number to bind the server on")
    parser.add_argument("--autoclean", help="interval between registration autoclean (0=disabled)",
                        default=0)
    args = parser.parse_args()
    run_name_server(args.host, args.port, args.autoclean)
