from pocs.utils import dither
from pocs.utils import signal_to_noise as snr

from astropy import units as u
from astropy.coordinates import SkyCoord
from pocs.utils.config import load_config


def create_imager_array(config=None):
    """ Create an instance of ImagerArray class present in the module 'snr'

    Args:
        config: information about the optics, cameras, bands, and imagers, required to create
        and ImagerArray object.

    Returns:
        ImagerArray
    """

    if config is None:
        config = load_config('performance')

    optics = dict()
    cameras = dict()
    filters = dict()
    psfs = dict()
    imagers = dict()

    # Setup imagers
    for name, imager_info in config['imagers'].items():
        optic_name = imager_info['optic']
        try:
            # Try to get from cache
            optic = optics[optic_name]
        except KeyError:
            # Create optic from this imager
            optic_info = config['optics'][optic_name]
            optic = snr.Optic(**optic_info)

            # Put in cache
            optics[optic_name] = optic
            camera_name = imager_info['camera']
        try:
            # Try to get from cache
            camera = cameras[camera_name]
        except KeyError:
            # Create camera for this imager
            camera_info = config['cameras'][camera_name]
            if type(camera_info['resolution']) == str:
                camera_info['resolution'] = [int(a) for a in camera_info['resolution'].split(',')]
            camera = snr.Camera(**camera_info)

            # Put in cache
            cameras[camera_name] = camera

        filter_name = imager_info['filter']
        try:
            # Try to get from cache
            band = filters[filter_name]
        except KeyError:
            # Create optic from this imager
            filter_info = config['filters'][filter_name]
            band = snr.Filter(**filter_info)

            # Put in cache
            filters[filter_name] = band

        psf_name = imager_info['psf']
        try:
            # Try to get from cache
            psf = psfs[psf_name]
        except KeyError:
            # Create optic from this imager
            psf_info = config['psfs'][psf_name]
            psf = snr.Moffat_PSF(**psf_info)

            # Put in cache
            psfs[psf_name] = psf

        imagers[name] = snr.Imager(optic,
                                   camera,
                                   band,
                                   psf,
                                   imager_info.get('num_imagers', 1),
                                   imager_info.get('num_per_computer', 1))
    imager_array = snr.ImagerArray(imagers)
    return imager_array


def get_hdr_target_list(imager_array, base_position, name, minimum_magnitude, primary_imager, n_long_exposures=1,
                        dither_parameters={'pattern': dither.dice9,
                                           'pattern_offset': 30 * u.arcminute,
                                           'random_offset': 6 * u.arcminute},
                        exp_time_ratio=2, maximum_exp_time=300 * u.second, priority=100, maximum_magnitude=None):
    """ Returns a target list

    Args:
        imager_array: An instance of ImagerArray class
        base_position (SkyCoord or compatible): sky coordinates of the target, should be a SkyCoord
        name: name of the target
        minimum_magnitude (Quantity): magnitude of the brightest point sources that we want to avoid saturating on
        primary_imager: name of the Imager that we want to use to generate the exposure time array
        n_long_exposures (optional, default 1): number of long exposures at the end of the HDR sequence
        dither_parameters (dict, optional): parameters required for the dither function
        exp_time_ratio (optional, default 2): ratio between successive exposure times in the HDR sequence
        maximum_exp_time (Quantity, optional, default 300s): exposure time to use for the long exposures
        priority (optional, default 1000): priority value assigned to the target
        maximum_magnitude (Quantity, optional): magnitude of the faintest point source we want to detect (SNR>=5.0). If
            specified will override n_long_exposures.

    Returns:
        list: list of dictionaries containing details (position, exposure time, etc.) for each exposure
    """

    if not isinstance(base_position, SkyCoord):
        base_position = SkyCoord(base_position)

    explist = imager_array.exposure_time_array(minimum_magnitude=minimum_magnitude,
                                               primary_imager=primary_imager,
                                               n_long_exposures=n_long_exposures,
                                               exp_time_ratio=exp_time_ratio,
                                               maximum_exp_time=maximum_exp_time,
                                               maximum_magnitude=maximum_magnitude)
    target_list = []
    position_list = dither.get_dither_positions(base_position=base_position,
                                                n_positions=len(explist),
                                                **dither_parameters)
    for i in range(0, len(explist)):
        target = {}
        if base_position.obstime is not None:
            target['epoch'] = base.obstime
        if base_position.equinox is not None:
            target['equinox'] = base_position.equinox
        target['frame'] = base_position.frame.name
        target['name'] = name
        target['position'] = position_list[i].to_string('hmsdms')
        target['priority'] = priority
        target['visit'] = {'primary_nexp': 1, 'primary_exptime': explist[i].value}
        target_list.append(target)

    return target_list
