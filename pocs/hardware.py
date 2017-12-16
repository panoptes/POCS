"""Information about hardware supported by Panoptes."""

ALL_NAMES = sorted(['camera', 'dome', 'mount', 'night', 'weather'])


def GetAllNames(all_names=ALL_NAMES, without=None):
    """
    """
    if without:
        return [v for v in all_names if v not in without]
    return list(all_names)


def GetSimulatorNames(simulator=None, kwargs=None, config=None):
    """Returns the names of the simulators to be used in lieu of hardware drivers.

    Note that returning a list containing 'X' doesn't mean that the config calls for a driver
    of type 'X'; that is up to the code working with the config to create drivers for real or
    simulated hardware.

    This funciton is intended to be called from PanBase or similar, which receives kwargs that
    may include simulator, config or both. For example:
           GetSimulatorNames(config=self.config, kwargs=kwargs)
    Or:
           GetSimulatorNames(simulator=simulator, config=self.config)

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
    def ExtractSimulator(d):
        if d:
            return d.get('simulator')
        return None
    for simulator in [simulator, ExtractSimulator(kwargs), ExtractSimulator(config)]:
        if not simulator:
            continue
        if isinstance(simulator, str):
            simulator = [simulator]
        if 'all' in simulator:
            return GetAllNames()
        else:
            return sorted(simulator)
    return []
