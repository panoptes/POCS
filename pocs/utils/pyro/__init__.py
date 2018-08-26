import os

import netifaces
import Pyro4
from Pyro4 import naming, errors

from pocs.camera.pyro import CameraServer
from pocs.utils.config import load_config


def get_own_ip(verbose=False, logger=None):
    """
    Attempts to automatically determine the IP address of the computer that it was run on.

    Args:
        verbose (bool, optional): If True print messages to standard output. Default false.
        logger (logging.Logger, optional): If given will log debug messages to the logger.

    Returns:
        host (str): IP address of the computer.

    Notes:
        This will probably return a useful value in most cases, however a computer can have
        several, equally valid IP addresses and it is not always possible to automatically
        determine the most appropriate one for the situation. This function simply looks for
        the default gateway, gets the IP addresses for the same interface as the default
        gateway, and returns the IP address that's in the same subnet as the gateway.
    """
    msg = 'Attempting to automatically determine IP address...'
    if verbose:
        print(msg)
    if logger:
        logger.debug(msg)
    # Hopefully there is a default gateway.
    default_gateway = netifaces.gateways()['default']
    # Get the gateway IP and associated inferface
    gateway_IP, interface = default_gateway[netifaces.AF_INET]
    msg = 'Found default gateway {} using interface {}'.format(gateway_IP, interface)
    if verbose:
        print(msg)
    if logger:
        logger.debug(msg)
    # Get the IP addresses from the interface
    addresses = []
    for address in netifaces.ifaddresses(interface)[netifaces.AF_INET]:
        addresses.append(address['addr'])
    # This will be a list with one or more entries. Probably want the one that starts
    # the same as the default gateway's IP.
    if len(addresses) > 1:
        msg = 'Interface has more than 1 IP address. Filtering on 1st byte...'
        if verbose:
            print(msg)
        if logger:
            logger.debug(msg)
        byte1, byte2 = gateway_IP.split('.')[0:2]
        addresses = [address for address in addresses if address.split('.')[0] == byte1]
        if len(addresses) > 1:
            msg = 'Interface still has more then 1 IP address. Filtering on 2nd byte...'
            if verbose:
                print(msg)
            if logger:
                logger.debug(msg)
            addresses = [address for address in addresses if address.split('.')[1] == byte2]

    assert len(addresses) == 1
    host = addresses[0]
    msg = 'Using IP address {} on interface {}'.format(addresses[0], interface)
    if verbose:
        print(msg)
    if logger:
        logger.debug(msg)
    return host


def run_name_server(host=None, port=None, autoclean=0):
    """
    Runs a Pyro name server.

    The name server must be running in order to use distributed cameras with POCS. The name server
    should be started before starting camera servers or POCS.

    Args:
        host (str, optional): hostname/IP address to bind the name server to. If not given then
            get_own_ip will be used to attempt to automatically determine the IP addresses of
            the computer that the name server is being started on.
        port (int, optional): port number to bind the name server to. If not given then the port
            will be selected automatically (usually 9090).
        autoclean (int, optional): interval, in seconds, for automatic deregistration of objects
            from the name server if they cannot be connected. If not given no autocleaning will
            be done.
    """
    try:
        # Check that there isn't a name server already running
        name_server = Pyro4.locateNS()
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

        Pyro4.config.NS_AUTOCLEAN = float(autoclean)

        print("Starting Pyro name server... (Control-C/Command-C to exit)")
        naming.startNSloop(host=host, port=port)
    else:
        print("Pyro name server {} already running! Exiting...".format(name_server))


def run_camera_server(ignore_local):
    """
    Runs a Pyro camera server.

    The camera server should be run on the camera control computers of distributed cameras. The
    camera servers should be started after the name server, but before POCS.

    Args:
        ignore_local (bool, optional): If True use the default $POCS/conf_files/pyro_camera.yaml
            only. If False will allow $POCS/conf_files/pyro_camera_local.yaml to override the
            default configuration. Default False.
    """
    Pyro4.config.SERVERTYPE = "multiplex"
    config = load_config(config_files=['pyro_camera.yaml'], ignore_local=ignore_local)
    host = config.get('host', None)
    if not host:
        host = get_own_ip(verbose=True)
    port = config.get('port', 0)

    with Pyro4.Daemon(host=host, port=port) as daemon:
        try:
            name_server = Pyro4.locateNS()
        except errors.NamingError as err:
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
