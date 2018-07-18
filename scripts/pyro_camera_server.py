#!/usr/bin/env python
import argparse
import Pyro4

from pocs.camera.simulator import Camera

parser = argparse.ArgumentParser()
parser.add_argument("host", help="hostname or IP address to bind the server on")
args = parser.parse_args()

ExposedCamera = Pyro4.expose(Camera)

name = "camera.simulator"

with Pyro4.Daemon(host=args.host) as daemon:
    name_server = Pyro4.locateNS()
    uri = daemon.register(ExposedCamera)
    name_server.register(name, uri, metadata={"POCS", "Camera", "simulator"})
    daemon.requestLoop()
