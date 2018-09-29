#!/usr/bin/env python3

########################################################################
# connect_clouddb_proxy.py
#
# This is a simple wrapper that looks up the connection information in the
# config and establishes a local proxy.
########################################################################


import os
import sys
import subprocess
from pprint import pprint

from pocs.utils.config import load_config


def main(instances, key_file, verbose=False):
    proxy_cmd = os.path.join(os.environ['POCS'], 'bin', 'cloud_sql_proxy')
    assert os.path.isfile(proxy_cmd)

    connection_str = ','.join(instances)
    instances_arg = '-instances={}'.format(connection_str)
    credentials_arg = '-credential_file={}'.format(key_file)

    run_proxy_cmd = [proxy_cmd, instances_arg, credentials_arg]

    if verbose:
        print("Running command: {}".format(run_proxy_cmd))

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
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--from_config', default=True, action='store_true',
                       help="Connect to all instances listed in the config file, default True.")
    group.add_argument('--database', default=None,
                       help="Connect to a specific database, otherwise connect to all in config.")
    parser.add_argument('--key_file', default=None, help="JSON service account key location.")
    parser.add_argument('--verbose', action='store_true', default=False,
                        help="Print results to stdout, default False.")
    args = parser.parse_args()

    config = load_config()
    try:
        network_config = config['panoptes_network']
        if args.verbose:
            print("Found config:")
            pprint(network_config)
    except KeyError as e:
        print("Invalid configuration. Check panoptes_network config. {}".format(e))
        sys.exit(1)

    # Try to lookup service account key from config if none provided
    key_file = args.key_file
    if not key_file:
        key_file = network_config['service_account_key']
        if not key_file or not os.path.isfile(key_file):
            print("Service account key not found in config, use --key_file.")
            sys.exit(1)

    try:

        project_id = network_config['project_id']

        # Get connection details
        connect_instances = list()
        for db_name in network_config['cloudsql_instances']:
            instance_info = network_config['cloudsql_instances'][db_name]

            if args.database and args.database != db_name:
                continue

            instance_name = instance_info['instance']
            location = instance_info['location']
            local_port = instance_info['local_port']

            conn_str = '{}:{}:{}=tcp:{}'.format(project_id, location, instance_name, local_port)
            connect_instances.append(conn_str)

    except KeyError as e:
        print("Invalid configuration. Check panoptes_network config. {}".format(e))
        sys.exit(1)

    if args.verbose:
        print("Connecting to the following instances:")
        pprint(connect_instances)

    main(connect_instances, key_file, verbose=args.verbose)
