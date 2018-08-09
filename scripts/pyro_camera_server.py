#!/usr/bin/env python
import argparse
from warnings import warn
import Pyro4

from pocs.utils import config
from pocs.camera.pyro import CameraServer

Pyro4.config.SERVERTYPE = "multiplex"

parser = argparse.ArgumentParser()
parser.add_argument("--ignore_local",
                    help="ignore pyro_camera_local.yaml config file",
                    action="store_true")
args = parser.parse_args()
config = config.load_config(config_files=['pyro_camera.yaml'], ignore_local=args.ignore_local)
port = config.get('port', 0)

with Pyro4.Daemon(host=config['host'], port=port) as daemon:
    try:
        name_server = Pyro4.locateNS()
    except Pyro4.errors.NamingError as err:
        warn('Failed to locate Pyro name server: {}'.format(err))
        exit(1)
    uri = daemon.register(CameraServer)
    name_server.register(config['name'], uri, metadata={"POCS",
                                                        "Camera",
                                                        config['camera']['model']})
    daemon.requestLoop()
