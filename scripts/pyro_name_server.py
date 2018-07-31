#!/usr/bin/env python
import argparse
import netifaces
from Pyro4 import naming, errors, config

parser = argparse.ArgumentParser()
parser.add_argument("--host", help="hostname or IP address to bind the server on")
parser.add_argument("--port", help="port number to bind the server on")
parser.add_argument("--autoclean", help="length of time between cleaning of registrations that are no longer available (0=disabled)")
args = parser.parse_args()

config.NS_AUTOCLEAN = float(args.autoclean)

try:
    # Check that there isn't a name server already running
    name_server = naming.locateNS()
except errors.NamingError:
    if not args.host:
        # Not given an hostname or IP address. Will attempt to work it out.
        print('Attempting to automatically determine IP address...')
        # Hopefully there is a default gateway.
        default_gateway = netifaces.gateways()['default']
        # Get the gateway IP and associated inferface
        gateway_IP, interface = default_gateway[netifaces.AF_INET]
        print('Found default gateway {} using interface {}'.format(gateway_IP, interface))
        # Get the IP addresses from the interface
        addresses = []
        for address in netifaces.ifaddresses(interface)[netifaces.AF_INET]:
            addresses.append(address['addr'])
        # This will be a list with one or more entries. Probably want the one that starts
        # the same as the default gateway's IP.
        if len(addresses) > 1:
            print('Interface has more than 1 IP address. Filtering on 1st byte...')
            byte1 = gateway_IP.split('.')[0]
            addresses = [address for address in addresses if address.split('.')[0] == byte1]
            if len(addresses) > 1:
                print('Interface still has more then 1 IP address. Filtering on 2nd byte...')
                byte2 = gateway_IP.split('.')[1]
                addresses = [address for address in addresses if address.split('.')[1] == byte2]

        assert len(addresses) == 1
        host = addresses[0]
        print('Using IP address {} on interface {}'.format(addresses[0], interface))
    else:
        host = str(args.host)

    print("Starting Pyro name server... (Control-C/Command-C to exit)")
    naming.startNSloop(host=host, port=int(args.port))
else:
    print("Pyro name server {} already running! Exiting...".format(name_server))
