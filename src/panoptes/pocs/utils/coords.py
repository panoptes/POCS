from datetime import datetime

from astropy import units as u
from astropy.coordinates import EarthLocation, SkyCoord, get_body, solar_system_ephemeris
from astropy.coordinates.name_resolve import NameResolveError
from astropy.time import Time
from astroquery.jplhorizons import Horizons
from panoptes.utils.time import current_time
from rich import print


def get_target_coords(
    target: str,
    obstime: datetime | Time | None = None,
    is_comet: bool = False,
    verbose: bool = False,
) -> SkyCoord:
    """Get the coordinates of the target.

    This helper accepts a variety of inputs and returns an astropy SkyCoord.

    Examples
    --------
    Using common target names (requires internet for name resolution):

    >>> from astropy.time import Time
    >>> c = get_target_coords("M42", obstime=Time("2020-01-01"))
    >>> type(c).__name__
    'SkyCoord'

    >>> get_target_coords("Andromeda Galaxy", obstime=Time("2020-01-01"), verbose=True)
    <SkyCoord (ICRS): (ra, dec) in deg
        (10.6847083, 41.26875)>

    >>> m = get_target_coords("Moon", obstime=Time("2020-01-01"))
    >>> isinstance(m, SkyCoord)
    True

    A local, non-network coordinate string example (always works offline):

    >>> get_target_coords("00h42m44.3s +41d16m9s", obstime=Time("2020-01-01"), verbose=True)
    <SkyCoord (ICRS): (ra, dec) in deg
        (10.68458333, 41.26916667)>

    >>> get_target_coords("10h00m00s +20d00m00s", obstime=Time("2020-01-01"))
    <SkyCoord (ICRS): (ra, dec) in deg
        (150., 20.)>

    Safety checks for hazardous or impossible targets:

    >>> get_target_coords("sun", obstime=Time("2020-01-01"))
    Traceback (most recent call last):
        ...
    RuntimeError: Refusing to go to the sun.

    >>> get_target_coords("earth", obstime=Time("2020-01-01"))
    Traceback (most recent call last):
        ...
    RuntimeError: It's hard for me to take a picture of earth.

    Args:
        target (str): The target to look for. If a comet, use a designator like `C/2025 N1` and
            set the `is_comet` flag to True.
        obstime (datetime, Time, optional): The time of the observation. Defaults to None.
        is_comet (bool, optional): Is the target a comet? Defaults to False.
        verbose (bool, optional): Print some information. Defaults to False.

    Returns:
        SkyCoord: The coordinates of the target.
    """
    obstime = obstime or current_time()

    # If the object is a solar system body, mark accordingly.
    is_solar_system_body = False

    if target.lower() in solar_system_ephemeris.bodies:
        is_solar_system_body = True

    if target.lower() == "sun":
        raise RuntimeError("Refusing to go to the sun.")

    if target.lower() == 'earth':
        raise RuntimeError("It's hard for me to take a picture of earth.")

    if is_comet:
        obj = Horizons(id=target, id_type="smallbody", epochs=obstime.jd1)
        eph = obj.ephemerides()
        coords = SkyCoord(eph[0]["RA"], eph[0]["DEC"], unit=(u.deg, u.deg))
    elif is_solar_system_body:
        coords = get_body(target.lower(), time=obstime)
    else:
        try:
            coords = SkyCoord(target)
        except ValueError:
            try:
                coords = SkyCoord.from_name(target)
            except NameResolveError:
                raise ValueError(f"Could not resolve target {target}")

    return coords
