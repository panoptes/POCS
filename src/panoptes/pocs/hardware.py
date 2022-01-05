"""Information about hardware supported by Panoptes."""
from enum import Enum

from panoptes.utils.config.client import get_config


class HardwareName(Enum):
    camera = 'camera'
    dome = 'dome'
    mount = 'mount'
    night = 'night'
    power = 'power'
    sensors = 'sensors'
    theskyx = 'theskyx'
    weather = 'weather'


def get_all_names(all_names=None, without=None):
    """Returns the names of all the categories of hardware that POCS supports.

    Note that this doesn't extend to the Arduinos for the telemetry and camera boards, for
    which no simulation is supported at this time.

    >>> from panoptes.pocs.hardware import get_all_names
    >>> get_all_names()
    ['camera', 'dome', 'mount', 'night', 'power', 'sensors', 'theskyx', 'weather']
    >>> get_all_names(without='mount')  # Single item
    ['camera', 'dome', 'night', 'power', 'sensors', 'theskyx', 'weather']
    >>> get_all_names(without=['mount', 'power'])  # List
    ['camera', 'dome', 'night', 'sensors', 'theskyx', 'weather']

    >>> # You can alter available hardware if needed.
    >>> get_all_names(['foo', 'bar', 'power'], without=['power'])
    ['bar', 'foo']

    Args:
        all_names (list): The list of hardware.
        without (iterable): Return all items expect those in the list.

    Returns:
        list: The sorted list of available hardware except those listed in `without`.
    """
    # Make sure that 'all' gets expanded.
    without = get_simulator_names(simulator=without)

    all_names = all_names or [h.name for h in HardwareName]

    return sorted([v for v in all_names if v not in without])


def get_simulator_names(simulator=None, kwargs=None):
    """Returns the names of the simulators to be used in lieu of hardware drivers.

    Note that returning a list containing 'X' doesn't mean that the config calls for a driver
    of type 'X'; that is up to the code working with the config to create drivers for real or
    simulated hardware.

    This function is intended to be called from `PanBase` or similar, which receives kwargs that
    may include simulator, config or both. For example::

        get_simulator_names(config=self.config, kwargs=kwargs)

        # Or:

        get_simulator_names(simulator=simulator, config=self.config)

    The reason this function doesn't just take **kwargs as its sole arg is that we need to allow
    for the case where the caller is passing in simulator (or config) twice, once on its own,
    and once in the kwargs (which won't be examined). Python doesn't permit a keyword argument
    to be passed in twice.

    >>> from panoptes.pocs.hardware import get_simulator_names
    >>> get_simulator_names()
    []
    >>> get_simulator_names('all')
    ['camera', 'dome', 'mount', 'night', 'power', 'sensors', 'theskyx', 'weather']

    Args:
        simulator (list): An explicit list of names of hardware to be simulated
            (i.e. hardware drivers to be replaced with simulators).
        kwargs: The kwargs passed in to the caller, which is inspected for an arg
            called 'simulator'.

    Returns:
        List of names of the hardware to be simulated.
    """
    empty = dict()

    def extract_simulator(d):
        return (d or empty).get('simulator')

    for v in [simulator, extract_simulator(kwargs), extract_simulator(get_config())]:
        if not v:
            continue
        if isinstance(v, str):
            v = [v]
        if 'all' in v:
            return [h.name for h in HardwareName]
        else:
            return sorted(v)
    return []
