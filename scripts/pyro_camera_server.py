#!/usr/bin/env python
import argparse
import Pyro4

from pocs.utils import config
from pocs.camera.pyro import CameraServer

parser = argparse.ArgumentParser()
parser.add_argument("--ignore_local",
                    help="ignore pyro_camera_local.yaml config file",
                    action="store_true")
args = parser.parse_args()
config = config.load_config(config_files=['pyro_camera.yaml'], ignore_local=args.ignore_local)

with Pyro4.Daemon(host=config['host'], port=config['port']) as daemon:
    name_server = Pyro4.locateNS()
    uri = daemon.register(CameraServer)
    name_server.register(config['name'], uri, metadata={"POCS", "Camera", "simulator"})
    daemon.requestLoop()
