#!/usr/bin/env python3

####################################
# connect_clouddb_proxy.py
#
# This is a simple wrapper that looks up
# the connection information in the config
# and establishes a local proxy.
#
####################################


import os
import sys
import subprocess
from pprint import pprint

from pocs.utils.config import load_config


def main(instance_id, local_port, verbose=False):
    proxy_cmd = os.path.join(os.environ['POCS'], 'bin', 'cloud_sql_proxy')
    connection_str = '-instances={}=tcp:{}'.format(instance_id, local_port)

    assert os.path.isfile(proxy_cmd)

    run_proxy_cmd = [proxy_cmd, connection_str]

    stdout_handler = subprocess.PIPE
    if verbose:
        stdout_handler = None

    try:
        subprocess.run(run_proxy_cmd, stdout=stdout_handler, stderr=stdout_handler)
    except KeyboardInterrupt:
        print("Shutting down")


if __name__ == '__main__':
    import argparse

    # Get the command line option
    parser = argparse.ArgumentParser(description="Connect to a google CloudSQL via a local proxy")
    parser.add_argument('-d', '--database', default=None, required=True,
                        help="Database, currently 'meta' or 'tess' from the config.")
    parser.add_argument('-v', '--verbose', action='store_true', default=False,
                        help="Print results to stdout")
    args = parser.parse_args()

    config = load_config()
    try:
        network_config = config['panoptes_network']
        if args.verbose:
            print("Found config:")
            pprint(network_config)
        instance_info = network_config['cloudsql_instances'][args.database]

        # Get connection details
        project_id = network_config['project_id']
        server_location = instance_info['location']
        db_name = instance_info['database']
        local_port = instance_info['local_port']

        instance_id = '{}:{}:{}'.format(project_id, server_location, db_name)

    except KeyError as e:
        print("Invalid configuration. Check panoptes_network config.")
        print(e)
        sys.exit(1)

    if args.verbose:
        print("Connecting to {} on local port {}".format(instance_id, local_port))

    main(instance_id, local_port, verbose=args.verbose)
