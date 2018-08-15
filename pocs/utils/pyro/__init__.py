import netifaces


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
