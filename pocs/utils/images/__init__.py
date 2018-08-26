import os
import subprocess
import shutil
import re

from matplotlib import pyplot as plt
from warnings import warn

from astropy import units as u
from astropy.wcs import WCS
from astropy.io.fits import open as open_fits
from astropy.visualization import (PercentileInterval, LogStretch, ImageNormalize)

from ffmpy import FFmpeg
from glob import glob
from copy import copy

from pocs.utils import current_time
from pocs.utils import error
from pocs.utils.images import fits as fits_utils
from pocs.utils.images import focus as focus_utils

palette = copy(plt.cm.inferno)
palette.set_over('w', 1.0)
palette.set_under('k', 1.0)
palette.set_bad('g', 1.0)


def crop_data(data, box_width=200, center=None, verbose=False):
    """ Return a cropped portion of the image

    Shape is a box centered around the middle of the data

    Args:
        data(np.array):     The original data, e.g. an image.
        box_width(int):     Size of box width in pixels, defaults to 200px
        center(tuple(int)): Crop around set of coords, defaults to image center.

    Returns:
        np.array:           A clipped (thumbnailed) version of the data
    """
    assert data.shape[0] >= box_width, "Can't clip data, it's smaller than {} ({})".format(
        box_width, data.shape)
    # Get the center
    if verbose:
        print("Data to crop: {}".format(data.shape))

    if center is None:
        x_len, y_len = data.shape
        x_center = int(x_len / 2)
        y_center = int(y_len / 2)
    else:
        y_center = int(center[0])
        x_center = int(center[1])

    box_width = int(box_width / 2)

    if verbose:
        print("Using center: {} {}".format(x_center, y_center))
        print("Box width: {}".format(box_width))

    center = data[x_center - box_width:x_center + box_width, y_center - box_width:
                  y_center + box_width]

    return center


def make_pretty_image(fname, timeout=15, **kwargs):  # pragma: no cover
    """ Make a pretty image

    This will create a jpg file from either a CR2 (Canon) or FITS file.

    Notes:
        See `$POCS/scripts/cr2_to_jpg.sh` for CR2 process

    Arguments:
        fname {str} -- Name of image file, may be either .fits or .cr2
        **kwargs {dict} -- Additional arguments to be passed to external script

    Keyword Arguments:
        timeout {number} -- Process timeout (default: {15})

    Returns:
        str -- Filename of image that was created

    """
    assert os.path.exists(fname),\
        warn("File doesn't exist, can't make pretty: {}".format(fname))

    if fname.endswith('.cr2'):
        pretty_path = _make_pretty_from_cr2(fname, timeout=timeout, **kwargs)
    elif fname.endswith('.fits'):
        pretty_path = _make_pretty_from_fits(fname, **kwargs)
    else:
        warn("File must be a Canon CR2 or FITS file.")
        return None

    # Symlink latest.jpg to the image; first remove the symlink if it already exists.
    if os.path.exists(pretty_path) and pretty_path.endswith('.jpg'):
        latest_path = '{}/images/latest.jpg'.format(os.getenv('PANDIR'))
        try:
            os.remove(latest_path)
        except FileNotFoundError:
            pass
        try:
            os.symlink(pretty_path, latest_path)
        except Exception as e:
            warn("Can't link latest image: {}".format(e))

        return pretty_path
    else:
        return None


def _make_pretty_from_fits(
        fname=None, figsize=(10, 10 / 1.325), dpi=150, alpha=0.2, number=7, **kwargs):

    with open_fits(fname) as hdu:
        header = hdu[0].header
        data = hdu[0].data
        data = focus_utils.mask_saturated(data)
        wcs = WCS(header)

    title = kwargs.get('title', header.get('FIELD', 'Unknown'))
    exp_time = header.get('EXPTIME', 'Unknown')

    filter_type = header.get('FILTER', 'Unknown filter')
    date_time = header.get('DATE-OBS', current_time(pretty=True)).replace('T', ' ', 1)

    percent_value = kwargs.get('normalize_clip_percent', 99.9)

    title = '{} ({}s {}) {}'.format(title, exp_time, filter_type, date_time)
    norm = ImageNormalize(interval=PercentileInterval(percent_value), stretch=LogStretch())

    fig = plt.figure(figsize=figsize, dpi=dpi)

    if wcs.is_celestial:
        ax = plt.subplot(projection=wcs)
        ax.coords.grid(True, color='white', ls='-', alpha=alpha)

        ra_axis = ax.coords['ra']
        ra_axis.set_axislabel('Right Ascension')
        ra_axis.set_major_formatter('hh:mm')
        ra_axis.set_ticks(
            number=number,
            color='white',
            exclude_overlapping=True
        )

        dec_axis = ax.coords['dec']
        dec_axis.set_axislabel('Declination')
        dec_axis.set_major_formatter('dd:mm')
        dec_axis.set_ticks(
            number=number,
            color='white',
            exclude_overlapping=True
        )
    else:
        ax = plt.subplot()
        ax.grid(True, color='white', ls='-', alpha=alpha)

        ax.set_xlabel('X / pixels')
        ax.set_ylabel('Y / pixels')

    im = ax.imshow(data, norm=norm, cmap=palette, origin='lower')
    fig.colorbar(im)
    plt.title(title)

    new_filename = fname.replace('.fits', '.jpg')
    plt.savefig(new_filename, bbox_inches='tight')
    plt.close()

    return new_filename


def _make_pretty_from_cr2(fname, timeout=15, **kwargs):  # pragma: no cover
    verbose = kwargs.get('verbose', False)

    title = '{} {}'.format(kwargs.get('title', ''), current_time().isot)

    solve_field = "{}/scripts/cr2_to_jpg.sh".format(os.getenv('POCS'))
    cmd = [solve_field, fname, title]

    if kwargs.get('primary', False):
        cmd.append('link')

    if verbose:
        print(cmd)

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if verbose:
            print(proc)
    except OSError as e:
        raise error.InvalidCommand("Can't send command to gphoto2. {!r} \t {}".format(e, cmd))
    except ValueError as e:
        raise error.InvalidCommand("Bad parameters to gphoto2. {!r} \t {}".format(e, cmd))
    except Exception as e:
        raise error.PanError("Timeout on plate solving: {!r}".format(e))

    return fname.replace('cr2', 'jpg')


def create_timelapse(directory, fn_out=None, file_type='jpg', **kwargs):
    """Create a timelapse

    A timelapse is created from all the jpg images in a given `directory`

    Args:
        directory (str): Directory containing jpg files
        fn_out (str, optional): Full path to output file name, if not provided,
            defaults to `directory` basename.
        file_type (str, optional): Type of file to search for, default 'jpg'.
        **kwargs (dict): Valid keywords: verbose

    Returns:
        str: Name of output file
    """
    if fn_out is None:
        head, tail = os.path.split(directory)
        if tail is '':
            head, tail = os.path.split(head)

        field_name = head.split('/')[-2]
        cam_name = head.split('/')[-1]
        fname = '{}_{}_{}.mp4'.format(field_name, cam_name, tail)
        fn_out = os.path.join(os.getenv('PANDIR'), 'images', 'timelapse', fname)

    fn_dir = os.path.dirname(fn_out)
    os.makedirs(fn_dir, exist_ok=True)
    inputs_glob = os.path.join(directory, '*.{}'.format(file_type))

    try:
        ff = FFmpeg(
            global_options='-r 3 -pattern_type glob',
            inputs={inputs_glob: None},
            outputs={
                fn_out: '-s hd1080 -vcodec libx264'
            })

        if 'verbose' in kwargs:
            out = None
            err = None
            print("Timelapse command: ", ff.cmd)
        else:
            out = open(os.devnull, 'w')
            err = open(os.devnull, 'w')

        ff.run(stdout=out, stderr=err)
    except Exception as e:
        warn("Problem creating timelapse in {}: {!r}".format(fn_out, e))
        fn_out = None

    return fn_out


def clean_observation_dir(dir_name, remove_jpgs=False, *args, **kwargs):
    """ Clean an observation directory.

    For the given `dir_name`, will:
        * Compress FITS files
        * Remove `.solved` files
        * Create timelapse from JPG files if present
        * Remove JPG files (optional)

    Args:
        dir_name (str): Full path to observation directory
        *args: Description
        **kwargs: Can include `verbose`
    """
    verbose = kwargs.get('verbose', False)

    def _print(msg):
        if verbose:
            print(msg)

    def _glob(s):
        return glob(os.path.join(dir_name, s))

    _print("Cleaning dir: {}".format(dir_name))

    # Pack the fits filts
    try:
        _print("Packing FITS files")
        for f in _glob('*.fits'):
            try:
                fits_utils.fpack(f)
            except Exception as e:  # pragma: no cover
                warn('Could not compress fits file: {!r}'.format(e))
    except Exception as e:
        warn('Problem with cleanup cleaning FITS: {!r}'.format(e))

    try:
        # Remove .solved files
        _print('Removing .solved files')
        for f in _glob('*.solved'):
            try:
                os.remove(f)
            except OSError as e:  # pragma: no cover
                warn('Could not delete file: {!r}'.format(e))
    except Exception as e:
        warn('Problem with cleanup removing solved: {!r}'.format(e))

    try:
        jpg_list = _glob('*.jpg')

        if len(jpg_list) > 0:

            # Create timelapse
            _print('Creating timelapse for {}'.format(dir_name))
            video_file = create_timelapse(dir_name)
            _print('Timelapse created: {}'.format(video_file))

            if remove_jpgs:
                # Remove jpgs
                _print('Removing jpgs')
                for f in jpg_list:
                    try:
                        os.remove(f)
                    except OSError as e:
                        warn('Could not delete file: {!r}'.format(e))
    except Exception as e:
        warn('Problem with cleanup creating timelapse: {!r}'.format(e))
