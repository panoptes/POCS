from dataclasses import dataclass
from astroplan import Observer
from astropy import units as u
from astropy.coordinates import EarthLocation
from astropy.utils.iers import Conf as iers_conf

from panoptes.utils import error
from panoptes.pocs.utils.logger import get_logger
from panoptes.utils.config.client import get_config

logger = get_logger()


@dataclass
class SiteDetails:
    observer: Observer
    earth_location: EarthLocation
    location: dict


def download_iers_a_file(iers_url: str = None):
    """ Download the IERS A file.

    This will download the IERS from the PANOPTES mirror and then set the
    auto download to False.
     """
    iers_url = iers_url or get_config('scheduler.iers_url')
    if iers_url is not None:
        logger.info(f'Getting IERS data at {iers_url=}')
        iers_conf.iers_auto_url.set(iers_url)
        logger.debug(f'Setting auto_download to "scheduler.iers_auto" to False')
        iers_conf.auto_download.set(get_config('scheduler.iers_auto', False))


def create_location_from_config() -> SiteDetails:
    """
    Sets up the site and location details.

    These items are read from the 'site' config directive and include:
        * name
        * latitude
        * longitude
        * timezone
        * pressure
        * elevation
        * horizon

     """

    logger.debug('Setting up site details')

    try:
        config_site = get_config('location', default=None)
        if config_site is None:
            raise error.PanError(msg='location information not found in config.')

        name = config_site.get('name', 'Nameless Location')

        latitude = config_site.get('latitude')
        longitude = config_site.get('longitude')

        timezone = config_site.get('timezone')

        pressure = config_site.get('pressure', 0.680) * u.bar
        elevation = config_site.get('elevation', 0 * u.meter)
        horizon = config_site.get('horizon', 30 * u.degree)
        flat_horizon = config_site.get('flat_horizon', -6 * u.degree)
        focus_horizon = config_site.get('focus_horizon', -12 * u.degree)
        observe_horizon = config_site.get('observe_horizon', -18 * u.degree)

        location = {
            'name': name,
            'latitude': latitude,
            'longitude': longitude,
            'elevation': elevation,
            'timezone': timezone,
            'pressure': pressure,
            'horizon': horizon,
            'flat_horizon': flat_horizon,
            'focus_horizon': focus_horizon,
            'observe_horizon': observe_horizon,
        }
        logger.debug(f"Location: {location}")

        # Create an EarthLocation for the mount
        earth_location = EarthLocation(lat=latitude, lon=longitude, height=elevation)
        observer = Observer(location=earth_location, name=name, timezone=timezone)

        site_details = SiteDetails(
            location=location,
            earth_location=earth_location,
            observer=observer
        )

        return site_details

    except Exception as e:
        raise error.PanError(msg=f'Bad site information: {e!r}')
