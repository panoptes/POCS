import glob
import os
import re
import shutil
import subprocess
import warnings

from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.table import Table as Table
from astropy.time import Time
from skimage.feature import register_translation

import matplotlib as mpl

from dateutil import parser as date_parser
mpl.use('Agg')
from matplotlib import pyplot as plt

import numpy as np
import pandas as pd
import seaborn as sb

from astropy.visualization import quantity_support

from scipy.optimize import curve_fit

from pocs.utils import current_time
from pocs.utils import error
from pocs.utils.error import *

from .conversions import *

# Plot support
sb.set()
quantity_support()

solve_re = [
    re.compile('RA,Dec = \((?P<center_ra>.*),(?P<center_dec>.*)\)'),
    re.compile('pixel scale (?P<pixel_scale>.*) arcsec/pix'),
    re.compile('Field rotation angle: up is (?P<rotation>.*) degrees E of N'),
]

def solve_field(fname, timeout=15, solve_opts=[], verbose=False, **kwargs):
    """ Plate solves an image.

    Args:
        fname(str, required):       Filename to solve in either .cr2 or .fits extension.
        timeout(int, optional):     Timeout for the solve-field command, defaults to 60 seconds.
        solve_opts(list, optional): List of options for solve-field.
        verbose(bool, optional):    Show output, defaults to False.
    """

    if fname.endswith('cr2'):
        if verbose:
            print("Converting cr2 to FITS")
        fname = cr2_to_fits(fname, verbose=verbose, **kwargs)
        if verbose:
            print("Solved filename: ", fname)

    solve_field = "{}/scripts/solve_field.sh".format(os.getenv('POCS'), '/var/panoptes/POCS')

    if not os.path.exists(solve_field):
        raise InvalidSystemCommand("Can't find solve-field: {}".format(solve_field))

    if solve_opts:
        options = solve_opts
    else:
        options = [
            '--guess-scale',
            '--cpulimit', str(timeout),
            '--no-verify',
            '--no-plots',
            '--crpix-center',
            '--downsample', '4',
        ]
        if kwargs.get('clobber', True):
            options.append('--overwrite')
        if kwargs.get('skip_solved', True):
            options.append('--skip-solved')
        if 'ra' in kwargs:
            options.append('--ra')
            options.append(str(kwargs.get('ra')))
        if 'dec' in kwargs:
            options.append('--dec')
            options.append(str(kwargs.get('dec')))
        if 'radius' in kwargs:
            options.append('--radius')
            options.append(str(kwargs.get('radius')))

        if os.getenv('PANTEMP'):
            options.append('--temp-dir')
            options.append(os.getenv('PANTEMP'))

    cmd = [solve_field, ' '.join(options), fname]
    if verbose:
        print("Cmd: ", cmd)

    try:
        proc = subprocess.Popen(cmd, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except OSError as e:
        raise error.InvalidCommand("Can't send command to solve_field.sh. {} \t {}".format(e, run_cmd))
    except ValueError as e:
        raise error.InvalidCommand("Bad parameters to solve_field.sh. {} \t {}".format(e, run_cmd))
    except Exception as e:
        raise error.PanError("Timeout on plate solving: {}".format(e))

    return proc


def get_solve_field(fname, **kwargs):
    """ Convenience function to wait for `solve_field` to finish.

    This function merely passes the `fname` of the image to be solved along to `solve_field`,
    which returns a subprocess.Popen object. This function then waits for that command
    to complete, populates a dictonary with the EXIF informaiton and returns.

    Parameters
    ----------
    fname : {str}
        Name of file to be solved, either a FITS or CR2
    **kwargs : {dict}
        Options to pass to `solve_field`

    Returns
    -------
    dict
        Keyword information from the solved field
    """

    verbose = kwargs.get('verbose', False)
    if verbose:
        print("Inside get_solve_field")

    proc = solve_field(fname, **kwargs)
    try:
        output, errs = proc.communicate(timeout=kwargs.get('timeout', 30))
    except subprocess.TimeoutExpired:
        proc.kill()
        output, errs = proc.communicate()

    out_dict = {}

    if errs is not None:
        warnings.warn("Error in solving: {}".format(errs))
    else:
        # Read the EXIF information from the CR2
        if fname.endswith('cr2'):
            out_dict.update(read_exif(fname))
            fname = fname.replace('cr2', 'new')  # astrometry.net default extension
            out_dict['solved_fits_file'] = fname

        try:
            out_dict.update(fits.getheader(fname))
        except OSError:
            if verbose:
                print("Can't read fits header for {}".format(fname))

        # Read items from the output
        # for line in output.split('\n'):
        #     for regexp in solve_re:
        #         matches = regexp.search(line)
        #         if matches:
        #             out_dict.update(matches.groupdict())
        #             if verbose:
        #                 print(matches.groupdict())

    return out_dict


def solve_offset(first_dict, second_dict, verbose=False): #unused
    """ Measures the offset of two images.

    This calculates the offset between the center of two images after plate-solving.

    Note:
        See `solve_field` for example of dict to be passed as argument.

    Args:
        first_dict(dict):   Dictonary describing the first image.
        second_dict(dict):   Dictonary describing the second image.

    Returns:
        out(dict):      Dictonary containing items related to the offset between the two images.
    """
    assert 'center_ra' in first_dict, warnings.warn("center_ra required for first image solving offset.")
    assert 'center_ra' in second_dict, warnings.warn("center_ra required for second image solving offset.")
    assert 'pixel_scale' in first_dict, warnings.warn("pixel_scale required for solving offset.")

    if verbose:
        print("Solving offset")

    first_ra = float(first_dict['center_ra']) * u.deg
    first_dec = float(first_dict['center_dec']) * u.deg

    second_ra = float(second_dict['center_ra']) * u.deg
    second_dec = float(second_dict['center_dec']) * u.deg

    rotation = float(first_dict['rotation']) * u.deg

    pixel_scale = float(first_dict['pixel_scale']) * (u.arcsec / u.pixel)

    first_time = Time(first_dict['DATE-OBS'])
    second_time = Time(second_dict['DATE-OBS'])

    out = {}

    # The pixel scale for the camera on our unit is:
    out['pixel_scale'] = pixel_scale
    out['rotation'] = rotation

    # Time between offset
    delta_t = ((second_time - first_time).sec * u.second).to(u.minute)
    out['delta_t'] = delta_t

    # Offset in degrees
    delta_ra = second_ra - first_ra
    delta_dec = second_dec - first_dec

    out['delta_ra_deg'] = delta_ra
    out['delta_dec_deg'] = delta_dec

    # Offset in pixels
    delta_ra = delta_ra.to(u.arcsec) / pixel_scale
    delta_dec = delta_dec.to(u.arcsec) / pixel_scale

    out['delta_ra'] = delta_ra
    out['delta_dec'] = delta_dec

    # Out unit drifted this many pixels in a minute:
    ra_rate = (delta_ra / delta_t)
    out['ra_rate'] = ra_rate

    dec_rate = (delta_dec / delta_t)
    out['dec_rate'] = dec_rate

    # Standard sidereal rate
    sidereal_rate = (24 * u.hour).to(u.minute) / (360 * u.deg).to(u.arcsec)
    out['sidereal_rate'] = sidereal_rate

    # Sidereal rate with our pixel_scale
    sidereal_scale = 1 / (sidereal_rate * pixel_scale)
    out['sidereal_scale'] = sidereal_scale

    # Difference between our rate and standard
    sidereal_factor = ra_rate / sidereal_scale
    out['sidereal_factor'] = sidereal_factor

    # Number of arcseconds we moved
    ra_delta_as = pixel_scale * delta_ra
    out['ra_delta_as'] = ra_delta_as

    # How many milliseconds at sidereal we are off
    # (NOTE: This should be current rate, not necessarily sidearal)
    ra_ms_offset = (ra_delta_as * sidereal_rate).to(u.ms)
    out['ra_ms_offset'] = ra_ms_offset

    # Number of arcseconds we moved
    dec_delta_as = pixel_scale * delta_dec
    out['dec_delta_as'] = dec_delta_as

    # How many milliseconds at sidereal we are off
    # (NOTE: This should be current rate, not necessarily sidearal)
    dec_ms_offset = (dec_delta_as * sidereal_rate).to(u.ms)
    out['dec_ms_offset'] = dec_ms_offset

    return out

def measure_offset(d0, d1, info={}, crop=True, pixel_factor=100, rate=None, verbose=False):
    """ Measures the offset of two images.

    This is a small wrapper around `scimage.feature.register_translation`. For now just
    crops the data to be the center image.

    Note
    ----
        This method will automatically crop_data data sets that are large. To prevent
        this, set crop_data=False.

    Parameters
    ----------
    d0 : {np.array}
        Array representing PGM data for first file (i.e. the first image)
    d1 : {np.array}
        Array representing PGM data for second file (i.e. the second image)
    info : {dict}, optional
        Optional information about the image, such as pixel scale, rotation, etc. (the default is {})
    crop : {bool}, optional
        Crop the image before offseting (the default is True, which crops the data to 500x500)
    pixel_factor : {number}, optional
        Subpixel factor (the default is 100, which will give precision to 1/100th of a pixel)
    rate : {number}, optional
        The rate at which the mount is moving (the default is sidereal rate)
    verbose : {bool}, optional
        Print messages (the default is False)

    Returns
    -------
    dict
        A dictionary of information related to the offset
    """

    assert d0.shape == d1.shape, 'Data sets must be same size to measure offset'

    if crop_data and d0.shape[0] > 500:
        d0 = crop_data(d0)
        d1 = crop_data(d1)

    offset_info = {}

    # Default for tranform matrix
    unit_pixel = 1 * (u.degree / u.pixel)

    # Get the WCS transformation matrix
    transform = np.array([
        [info.get('cd11', unit_pixel).value, info.get('cd12', unit_pixel).value],
        [info.get('cd21', unit_pixel).value, info.get('cd22', unit_pixel).value]
    ])

    # We want the negative of the applied orientation
    # theta = info.get('orientation', 0 * u.deg) * -1

    # Rotate the images so N is up (+y) and E is to the right (+x)
    # rd0 = rotate(d0, theta.value)
    # rd1 = rotate(d1, theta.value)

    shift, error, diffphase = register_translation(d0, d1, pixel_factor)

    offset_info['shift'] = (shift[0], shift[1])
    # offset_info['error'] = error
    # offset_info['diffphase'] = diffphase

    if transform is not None:

        coords_delta = np.array(shift).dot(transform)
        if verbose:
            print("Δ coords: {}".format(coords_delta))

        # pixel_scale = float(info.get('pixscale', 10.2859)) * (u.arcsec / u.pixel)

        sidereal = (15 * (u.arcsec / u.second))

        # Default to guide rate (0.9 * sidereal)
        if rate is None:
            rate = 0.9 * sidereal

        # # Number of arcseconds we moved
        ra_delta_as = (coords_delta[0] * u.deg).to(u.arcsec)
        dec_delta_as = (coords_delta[1] * u.deg).to(u.arcsec)
        offset_info['ra_delta_as'] = ra_delta_as
        offset_info['dec_delta_as'] = dec_delta_as

        # # How many milliseconds at current rate we are off
        ra_ms_offset = (ra_delta_as / rate).to(u.ms)
        dec_ms_offset = (dec_delta_as / rate).to(u.ms)
        offset_info['ra_ms_offset'] = ra_ms_offset.round()
        offset_info['dec_ms_offset'] = dec_ms_offset.round()

        delta_time = info.get('delta_time', 125 * u.second)

        ra_rate_rate = ra_delta_as / delta_time
        dec_rate_rate = dec_delta_as / delta_time

        ra_delta_rate = 1.0 - ((sidereal + ra_rate_rate) / sidereal)  # percentage of sidereal
        dec_delta_rate = 1.0 - ((sidereal + dec_rate_rate) / sidereal)  # percentage of sidereal
        offset_info['ra_delta_rate'] = round(ra_delta_rate.value, 4)
        offset_info['dec_delta_rate'] = round(dec_delta_rate.value, 4)

    return offset_info

def get_pointing_error(fits_fname, verbose=False): #unused
    """Gets the pointing error for the plate-solved FITS file.

    Gets the image center coordinates and compares this to the 'RA' and 'DEC' FITS
    headers in the same file. This is the difference between the target and actual.
    The separation (deg) is returned.

    Note
    ----
    Requires astrometry.net and utility scripts to be installed.

    Parameters
    ----------
    fits_fname : {str}
        Name of a FITS file that contains a WCS.

    Returns
    -------
    u.Quantity
        The degree separation of the target from the center of the image
    """
    assert os.path.exists(fits_fname), warnings.warn("No file exists at: {}".format(fits_fname))

    # Get the WCS info and the HEADER info
    wcs_info = get_wcsinfo(fits_fname)
    hdu = fits.open(fits_fname)[0]

    # Create two coordinates
    center = SkyCoord(ra=wcs_info['ra_center'], dec=wcs_info['dec_center'])
    target = SkyCoord(ra=float(hdu.header['RA']) * u.degree, dec=float(hdu.header['Dec']) * u.degree)

    if verbose:
        print("Center coords: {}".format(center))
        print("Target coords: {}".format(target))

    return center.separation(target)


def process_cr2(cr2_fname, fits_headers={}, solve=True, make_pretty=False, verbose=False, **kwargs):
    assert os.path.exists(cr2_fname), warnings.warn("File must exist: {}".format(cr2_fname))

    processed_info = {}

    try:
        if verbose:
            print("Processing image")

        if make_pretty:
            # If we have the object name, pass it to pretty image
            if 'title' in fits_headers:
                kwargs['title'] = "{}".format(fits_headers.get('title'))

            pretty_image = make_pretty_image(cr2_fname, **kwargs)
            processed_info['pretty_image'] = pretty_image

        if solve:
            try:
                solve_info = get_solve_field(cr2_fname, fits_headers=fits_headers, **kwargs)
                if verbose:
                    print("Solve info: {}".format(solve_info))

                processed_info.update(solve_info)
            except error.PanError as e:
                warnings.warn("Timeout while solving: {}".format(e))
            except Exception as e:
                raise error.PanError("Can't solve field: {}".format(e))
    except Exception as e:
        warnings.warn("Problem in processing: {}".format(e))

    return processed_info


def get_pec_data(image_dir, ref_image='guide_000.new',
                 observer=None, phase_length=480,
                 skip_solved=True, verbose=False, parallel=False, **kwargs):

    base_dir = os.getenv('PANDIR', '/var/panoptes')

    target_name, obs_date_start = image_dir.rstrip('/').split('/', 1)

    target_dir = '{}/images/fields/{}'.format(base_dir, image_dir)

    guide_images = glob.glob('{}/guide_*.cr2'.format(target_dir))
    image_files = glob.glob('{}/1*.cr2'.format(target_dir))
    guide_images.sort()
    image_files.sort()
    if verbose:
        print("Found {} files.".format(len(image_files)))

    # WCS Information
    ref_image = guide_images[-1]
    if verbose:
        print("Ref image: {}".format(ref_image))

    ref_solve_info = None

    # Solve the guide image if given a CR2
    if ref_image.endswith('cr2'):
        if verbose:
            print("Solving guide image")
        ref_solve_info = get_solve_field(ref_image, verbose=verbose)
        if verbose:
            print("ref_solve_info: {}".format(ref_solve_info))
        ref_image = ref_image.replace('cr2', 'new')

    # If no guide image, attempt a solve on similar fits
    if not os.path.exists(ref_image):
        if os.path.exists(ref_image.replace('new', 'fits')):
            ref_solve_info = get_solve_field(ref_image.replace('new', 'fits'))

    if verbose and ref_solve_info:
        print(ref_solve_info)

    assert os.path.exists(ref_image), warnings.warn("Ref image does not exist: {}".format(ref_image))

    ref_header = fits.getheader(ref_image)
    ref_info = get_wcsinfo(ref_image)
    if verbose:
        print(ref_image)
        # print(ref_header)

    # Reference time
    t0 = Time(ref_header.get('DATE-OBS', date_parser.parse(obs_date_start))).datetime

    img_info = []

    def solver(img):
        if verbose:
            print('*' * 80)
        header_info = {}
        if not os.path.exists(img.replace('cr2', 'wcs')):
            if verbose:
                print("No WCS, solving CR2: {}".format(img))

            header_info = get_solve_field(
                img,
                ra=ref_info['ra_center'].value,
                dec=ref_info['dec_center'].value,
                radius=10,
                verbose=verbose,
                **kwargs
            )

        # Get the WCS info for image
        if len(header_info) == 0:
            header_info.update(get_wcsinfo(img.replace('cr2', 'wcs')))
            header_info.update(fits.getheader(img.replace('cr2', 'new')))
            header_info.update(read_exif(img))

        hi = dict((k.lower(), v) for k, v in header_info.items())
        if verbose:
            print(hi)

        img_info.append(hi)

    # if parallel:
    #     with concurrent.futures.ProcessPoolExecutor() as executor:
    #         executor.map(solver, image_files)
    # else:
    for img in image_files:
        solver(img)

    ras = [w['ra_center'].value for w in img_info]
    decs = list([w['dec_center'].value for w in img_info])

    ras_as = [w['ra_center'].to(u.arcsec).value for w in img_info]
    decs_as = [w['dec_center'].to(u.arcsec).value for w in img_info]

    time_range = [Time(w.get('date-obs', t0)) for w in img_info]

    ha = []

    if observer is not None:
        ha = np.array([observer.target_hour_angle(t, SkyCoord(ras[idx], decs[idx], unit='degree')).to(u.degree).value
                       for idx, t in enumerate(time_range)])

        ha[ha > 270] = ha[ha > 270] - 360

    # Delta time
    dt = np.diff([t.datetime.timestamp() for t in time_range])
    dt = np.insert(dt, 0, (time_range[0].datetime.timestamp() - t0.timestamp()))
    t_offset = np.cumsum(dt)

    # Diff between each exposure
    ra_diff = np.diff(ras_as)
    ra_diff = np.insert(ra_diff, 0, 0)

    dec_diff = np.diff(decs_as)
    dec_diff = np.insert(dec_diff, 0, 0)

    # Delta arcsecond
    dra_as = pd.Series(ra_diff)
    ddec_as = pd.Series(dec_diff)

    # Delta arcsecond rate
    dra_as_rate = dra_as / dt
    ddec_as_rate = ddec_as / dt

    dra_as_rate.fillna(value=0, inplace=True)
    ddec_as_rate.fillna(value=0, inplace=True)

    if verbose:
        print(type(ra_diff))
        print(type(dec_diff))
        print(type(dt))
        print(type(t_offset))
        print(type(ras))
        print(type(decs))

    table = Table({
        'dec': decs,
        'dec_as': ddec_as,
        'dec_as_rate': ddec_as_rate,
        'dt': dt,
        'ha': ha,
        'ra': ras,
        'ra_as': dra_as,
        'ra_as_rate': dra_as_rate,
        'offset': t_offset,
        'time_range': [t.mjd for t in time_range],
    }, meta={
        'name': target_name,
        'obs_date_start': obs_date_start,
    })

    table.add_index('time_range')

    table['ra'].format = '%+3.3f'
    table['ha'].format = '%+3.3f'
    table['dec'].format = '%+3.3f'
    table['dec_as_rate'].format = '%+1.5f'
    table['ra_as_rate'].format = '%+1.5f'
    table['time_range'].format = '%+5.5f'
    table['ra_as'].format = '%+2.3f'
    table['dec_as'].format = '%+3.3f'

    return table


def get_pec_fit(data, gear_period=480, with_plot=False, **kwargs):
    """
    Adapted from:
    http://stackoverflow.com/questions/16716302/how-do-i-fit-a-sine-curve-to-my-data-with-pylab-and-numpy
    """

    if with_plot:
        fig, axes = plt.subplots(nrows=2, ncols=1, sharex=True)

    for idx, key in enumerate(['as', 'as_rate']):

        ra_field = 'ra_{}'.format(key)
        dec_field = 'dec_{}'.format(key)

        guess_freq = 2
        guess_phase = 0
        guess_amplitude_ra = 3 * data[ra_field].std() / (2**0.5)
        guess_offset_ra = data[ra_field].mean()

        guess_amplitude_dec = 3 * data[dec_field].std() / (2**0.5)
        guess_offset_dec = data[dec_field].mean()

        # Initial guess parameters
        ra_p0 = [guess_freq, guess_amplitude_ra, guess_phase, guess_offset_ra]
        dec_p0 = [guess_freq, guess_amplitude_dec, guess_phase, guess_offset_dec]

        # Worm gear is a periodic sine function
        def gear_sin(x, freq, amplitude, phase, offset):
            return amplitude * np.sin(x * freq + phase) + offset

        # Fit to function
        fit_range = data['ha']
        ra_fit = curve_fit(gear_sin, fit_range, data[ra_field], p0=ra_p0)
        dec_fit = curve_fit(gear_sin, fit_range, data[dec_field], p0=dec_p0)

        smooth_range = np.linspace(fit_range.min(), fit_range.max(), 1000)
        smooth_ra_fit = gear_sin(smooth_range, *ra_fit[0])
        smooth_dec_fit = gear_sin(smooth_range, *dec_fit[0])

        # The `gradient` method takes the derivate, giving the rate
        if key == 'as_rate':
            smooth_ra_fit = np.gradient(smooth_ra_fit)
            smooth_dec_fit = np.gradient(smooth_dec_fit)

        if with_plot:
            ra_max = np.max(smooth_ra_fit)
            ra_min = np.min(smooth_ra_fit)

            ax = axes[idx]

            if key == 'as':
                ax.plot(fit_range, data[ra_field], 'o', color='red', alpha=0.5)

            ax.plot(smooth_range, smooth_ra_fit, label='RA Fit', color='blue')
            ax.plot(smooth_range, smooth_dec_fit, label='Dec Fit', color='green')

            ax.set_title("Peak-to-Peak: {} arcsec".format(round(ra_max - ra_min, 3)))
            ax.set_xlabel('HA')
            ax.set_ylabel('RA Offset Rate [arcsec]')
            ax.legend()

    if with_plot:
        plt.suptitle(kwargs.get('plot_title', 'PEC Fit'))
        plt.savefig('{}/images/{}'.format(os.getenv('PANDIR', default='/var/panoptes/'),
                                          kwargs.get('plot_name', 'pec_fit.png')))

    ra_optimized = ra_fit[0]

    return ra_optimized


def make_pec_fit_fn(params): #unused
    """ Creates a PEC function based on passed params """

    def fit_fn(x):
        return params[1] * np.sin(x * params[0] + params[2]) + params[3]

    return fit_fn
