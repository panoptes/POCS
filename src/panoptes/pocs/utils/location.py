"""Location helpers for creating and configuring site/observer objects.

This module provides utilities to construct an astroplan Observer and related
astropy EarthLocation from PANOPTES configuration, and to configure IERS table
fetching used by astropy/astroplan for accurate time/earth orientation.
"""

from dataclasses import dataclass
from astroplan import Observer
from astropy import units as u
from astropy.coordinates import EarthLocation
from astropy.utils.iers import Conf as iers_conf

from panoptes.utils import error
from panoptes.pocs.utils.logger import get_logger
from panoptes.utils.config.client import get_config
from panoptes.utils.utils import get_quantity_value

logger = get_logger()


@dataclass
class SiteDetails:
    """Container for site-specific objects and metadata.

    Attributes:
        observer (astroplan.Observer): The astroplan Observer for the site.
        earth_location (astropy.coordinates.EarthLocation): The underlying EarthLocation.
        location (dict): Raw location configuration values used to construct the above.
    """

    observer: Observer
    earth_location: EarthLocation
    location: dict


def download_iers_a_file(iers_url: str = None):
    """Download and configure the IERS A table URL.

    This points astropy's IERS auto URL at a PANOPTES mirror (if configured)
    and sets the auto-download behavior based on config.

    Args:
        iers_url (str | None): Optional override URL for the IERS A file. If not
            provided, uses the value from configuration key 'scheduler.iers_url'.

    Returns:
        None

    Notes:
        Also sets astropy's iers_conf.auto_download to the value of
        'scheduler.iers_auto' (default False).
    """
    iers_url = iers_url or get_config("scheduler.iers_url")
    if iers_url is not None:
        logger.info(f"Getting IERS data at {iers_url=}")
        iers_conf.iers_auto_url.set(iers_url)
        logger.debug('Setting auto_download to "scheduler.iers_auto" to False')
        iers_conf.auto_download.set(get_config("scheduler.iers_auto", False))


def create_location_from_config() -> SiteDetails:
    """Construct site objects (Observer, EarthLocation) from configuration.

    Reads the 'location' section from the PANOPTES configuration and constructs a
    dictionary of location parameters as well as the corresponding astropy EarthLocation
    and astroplan Observer.

    Returns:
        SiteDetails: Container with observer, earth_location, and the raw location dict.

    Raises:
        panoptes.utils.error.PanError: If the location information is missing or invalid.

    Notes:
        Expected location keys include: name, latitude, longitude, timezone, pressure,
        elevation, and horizon values (horizon, flat_horizon, focus_horizon, observe_horizon).
    """

    logger.debug("Setting up site details")

    try:
        config_site = get_config("location", default=None)
        if config_site is None:
            raise error.PanError(msg="location information not found in config.")

        name = config_site.get("name", "Nameless Location")

        def get_config_with_unit(key, default_value=None, default_unit=None):
            """Small helper function to get the config item and ensure a unit."""
            v = config_site.get(key, default_value)
            if default_unit is not None:
                v = get_quantity_value(v) * default_unit

            return v

        timezone = get_config_with_unit("timezone")

        latitude = get_config_with_unit("latitude", default_unit=u.degree)
        longitude = get_config_with_unit("longitude", default_unit=u.degree)
        elevation = get_config_with_unit("elevation", default_value=0, default_unit=u.meter)

        pressure = get_config_with_unit("pressure", default_value=0.68, default_unit=u.bar)

        horizon = get_config_with_unit("horizon", default_value=30, default_unit=u.degree)
        flat_horizon = get_config_with_unit("flat_horizon", default_value=-6, default_unit=u.degree)
        focus_horizon = get_config_with_unit(
            "focus_horizon", default_value=-12, default_unit=u.degree
        )
        observe_horizon = get_config_with_unit(
            "observe_horizon", default_value=-18, default_unit=u.degree
        )

        location = {
            "name": name,
            "latitude": latitude,
            "longitude": longitude,
            "elevation": elevation,
            "timezone": timezone,
            "pressure": pressure,
            "horizon": horizon,
            "flat_horizon": flat_horizon,
            "focus_horizon": focus_horizon,
            "observe_horizon": observe_horizon,
        }
        logger.debug(f"Location: {location}")

        # Create an EarthLocation for the mount
        earth_location = EarthLocation(lat=latitude, lon=longitude, height=elevation)
        observer = Observer(location=earth_location, name=name, timezone=timezone)

        site_details = SiteDetails(
            location=location, earth_location=earth_location, observer=observer
        )

        return site_details

    except Exception as e:
        raise error.PanError(msg=f"Bad site information: {e!r}")
