#!/usr/bin/env python

from pocs.utils.messaging import PanMessaging

from_port = 6510
to_port = 6511

print("Starting message forwarding, hit Ctrl-c to stop")
print("Port: {} -> {}".format(from_port, to_port))

try:
    f = PanMessaging.create_forwarder(from_port, to_port)
except KeyboardInterrupt:
    print("Shutting down and exiting...")
