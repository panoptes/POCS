#!/usr/bin/env python
import argparse
from warnings import warn

import Pyro4

from pocs.utils.config import load_config
from pocs.utils.pyro import get_own_ip
from pocs.camera.pyro import CameraServer


def run_camera_server(ignore_local):
    Pyro4.config.SERVERTYPE = "multiplex"
    config = load_config(config_files=['pyro_camera.yaml'], ignore_local=ignore_local)
    host = config.get('host')
    if not host:
        host = get_own_ip(verbose=True)
    port = config.get('port', 0)

    with Pyro4.Daemon(host=host, port=port) as daemon:
        try:
            name_server = Pyro4.locateNS()
        except Pyro4.errors.NamingError as err:
            warn('Failed to locate Pyro name server: {}'.format(err))
            exit(1)
        print('Found Pyro name server')
        uri = daemon.register(CameraServer)
        print('Camera server registered with daemon as {}'.format(uri))
        name_server.register(config['name'], uri, metadata={"POCS",
                                                            "Camera",
                                                            config['camera']['model']})
        print('Registered with name server as {}'.format(config['name']))
        print('Starting request loop... (Control-C/Command-C to exit)')
        daemon.requestLoop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ignore_local",
                        help="ignore pyro_camera_local.yaml config file",
                        action="store_true")
    args = parser.parse_args()
    run_camera_server(args.ignore_local)
