"""Information about hardware supported by Panoptes."""

from enum import Enum

from panoptes.utils.config.store import get_config


class HardwareName(Enum):
    """Enumeration of top-level hardware categories supported by POCS.

    Members correspond to hardware subsystems that may have real drivers or
    simulators enabled via configuration (see get_simulator_names).
    """

    camera = "camera"
    dome = "dome"
    mount = "mount"
    night = "night"
    power = "power"
    sensors = "sensors"
    theskyx = "theskyx"
    weather = "weather"


def get_all_names(all_names=None, without=None):
    """Return the names of all the categories of hardware that POCS supports.

    Note:
        This doesn't extend to the Arduinos for the telemetry and camera boards, for
        which no simulation is supported at this time.

    Examples:
        >>> from panoptes.pocs.hardware import get_all_names
        >>> get_all_names()
        ['camera', 'dome', 'mount', 'night', 'power', 'sensors', 'theskyx', 'weather']
        >>> get_all_names(without='mount')  # Single item
        ['camera', 'dome', 'night', 'power', 'sensors', 'theskyx', 'weather']
        >>> get_all_names(without=['mount', 'power'])  # List
        ['camera', 'dome', 'night', 'sensors', 'theskyx', 'weather']

        # You can alter available hardware if needed.
        >>> get_all_names(['foo', 'bar', 'power'], without=['power'])
        ['bar', 'foo']

    Args:
        all_names (list): The list of hardware.
        without (Iterable): Return all items except those in the list.

    Returns:
        list: The sorted list of available hardware except those listed in `without`.
    """
    # Make sure that 'all' gets expanded.
    without = get_simulator_names(simulator=without)

    all_names = all_names or [h.name for h in HardwareName]

    return sorted([v for v in all_names if v not in without])


def get_simulator_names(simulator: str | list[str] | None = None, kwargs: dict | None = None) -> list[str]:
    """Return the names of the simulators to be used in lieu of hardware drivers.

    Checks sources in priority order: the explicit ``simulator`` argument, then
    ``kwargs["simulator"]``, then the ``simulator`` key in the config store.  The
    config store is only queried when the earlier sources are all falsy (lazy
    evaluation), so this function is safe to call before the config store is
    fully initialised.

    Note:
        Returning a list containing 'X' doesn't mean that the config calls for a driver
        of type 'X'; that is up to the code working with the config to create drivers for real or
        simulated hardware.

    Examples:
        >>> from panoptes.pocs.hardware import get_simulator_names
        >>> get_simulator_names()
        []
        >>> get_simulator_names('all')
        ['camera', 'dome', 'mount', 'night', 'power', 'sensors', 'theskyx', 'weather']
        >>> get_simulator_names(['mount', 'camera'])
        ['camera', 'mount']

    Args:
        simulator: An explicit simulator name or list of names. Pass ``"all"`` to
            simulate every hardware subsystem.
        kwargs: Optional dict (e.g. the caller's ``**kwargs``) inspected for a
            ``"simulator"`` key.

    Returns:
        Sorted list of hardware names to be simulated, or an empty list.
    """
    all_names = [h.name for h in HardwareName]

    def _candidates():
        yield simulator
        yield (kwargs or {}).get("simulator")
        yield get_config("simulator")  # only reached when above are both falsy

    for v in _candidates():
        if not v:
            continue
        if isinstance(v, str):
            v = [v]
        if "all" in v:
            return all_names
        return sorted(name for name in v if name in all_names)
    return []
