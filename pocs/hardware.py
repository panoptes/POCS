"""Information about hardware supported by Panoptes."""

ALL_NAMES = sorted([
    'camera',
    'dome',
    'mount',
    'night',
    'power',
    'theskyx',
    'weather',
])


def get_all_names(all_names=ALL_NAMES, without=list()):
    """Returns the names of all the categories of hardware that POCS supports.

    Note that this doesn't extend to the Arduinos for the telemetry and camera boards, for
    which no simulation is supported at this time.
    """
    # Make sure that 'all' gets expanded.
    if without:
        without = get_simulator_names(simulator=without)

    return [v for v in all_names if v not in without]


def get_simulator_names(simulator=None, kwargs=None, config=None):
    """Returns the names of the simulators to be used in lieu of hardware drivers.

    Note that returning a list containing 'X' doesn't mean that the config calls for a driver
    of type 'X'; that is up to the code working with the config to create drivers for real or
    simulated hardware.

    This function is intended to be called from PanBase or similar, which receives kwargs that
    may include simulator, config or both. For example:
           get_simulator_names(config=self.config, kwargs=kwargs)
    Or:
           get_simulator_names(simulator=simulator, config=self.config)

    The reason this function doesn't just take **kwargs as its sole arg is that we need to allow
    for the case where the caller is passing in simulator (or config) twice, once on its own,
    and once in the kwargs (which won't be examined). Python doesn't permit a keyword argument
    to be passed in twice.

    Args:
        simulator:
            An explicit list of names of hardware to be simulated (i.e. hardware drivers
            to be replaced with simulators).
        kwargs:
            The kwargs passed in to the caller, which is inspected for an arg called 'simulator'.
        config:
            Dictionary created from pocs.yaml or similar.

    Returns:
        List of names of the hardware to be simulated.
    """
    empty = dict()

    def extract_simulator(d):
        return (d or empty).get('simulator')

    for v in [simulator, extract_simulator(kwargs), extract_simulator(config)]:
        if not v:
            continue
        if isinstance(v, str):
            v = [v]
        if 'all' in v:
            return ALL_NAMES
        else:
            return sorted(v)
    return []
