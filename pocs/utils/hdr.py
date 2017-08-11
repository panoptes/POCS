from pocs.utils import dither
from pocs.utils import signal_to_noise as snr

from astropy import units as u
from astropy.coordinates import SkyCoord


def get_target_list(target_name,
                    imagers,
                    primary_imager,
                    base_position,
                    exposure_parameters={'shortest_exp_time': 5 * u.second,
                                         'longest_exp_time': 600 * u.second,
                                         'num_long_exp': 1,
                                         'exp_time_ratio': 2.0,
                                         'snr_target': 5.0},
                    dither_parameters={'pattern': dither.dice9,
                                       'pattern_offset': 30 * u.arcminute,
                                       'random_offset': 3 * u.arcminute},
                    priority=100):
    """
    Generates a list of dictionaries containing the details for a dithered, HDR sequence of exposures.

    Args:
        target_name (str): name of the target objects
        imagers (dictionary): dictionary of `signal-to-noise.Imager` objects, as returned from
            `signal-to-noise.create_imagers()`
        primary_imager: name of the Imager object from imagers that should be used to calculate the exposure times.
        base_position (SkyCoord or compatible): base position for the dither pattern, either a SkyCoord or an object
             that can be converted to one by the SkyCoord constructor (e.g. string)
        exposure_parameters (dict): dictionary of keyword parameters to pass to `Imager.exp_time_sequence()`. See
            that method's docstring for details of all the accepted parameters.
        dither_parameters (dict): dictionary of keyword parameters to pass to `dither.get_dither_positions()``. See
            that function's docstring for details of all the accepted parameters.
        priority (optional, default 100): scheduler priority to assign to the exposures.

    Returns:
        list: list of dictionaries, each containing the details for an individual exposure.
    """
    try:
        imager = imagers[primary_imager]
    except KeyError:
        raise ValueError("Could not find imager '{}' in imagers dictionary!".format(primary_imager))

    if not isinstance(base_position, SkyCoord):
        try:
            base_position = SkyCoord(base_position)
        except ValueError:
            raise ValueError("Base position '{}' could not be converted to a SkyCoord object!".format(base_position))

    explist = imager.exp_time_sequence(**exposure_parameters)

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
        target['name'] = target_name
        target['position'] = position_list[i].to_string('hmsdms')
        target['priority'] = priority
        target['exp_time'] = explist[i].value,
        target_list.append(target)

    return target_list
