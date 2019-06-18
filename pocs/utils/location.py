from astroplan import Observer
from astropy import units as u
from astropy.coordinates import EarthLocation

from pocs.utils import error
from pocs.utils.logger import get_root_logger


def create_location_from_config(config, logger=None):
    """
     Sets up the site and location details.

     Note:
         These items are read from the 'site' config directive and include:
             * name
             * latitude
             * longitude
             * timezone
             * presseure
             * elevation
             * horizon

     """
    if logger is None:
        logger = get_root_logger()

    logger.debug('Setting up site details')

    try:
        config_site = config.get('location')

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
        logger.debug("Location: {}".format(location))

        # Create an EarthLocation for the mount
        earth_location = EarthLocation(
            lat=latitude, lon=longitude, height=elevation)
        observer = Observer(
            location=earth_location, name=name, timezone=timezone)

        site_details = {
            "location": location,
            "earth_location": earth_location,
            "observer": observer
        }

        return site_details

    except Exception:
        raise error.PanError(msg='Bad site information')
