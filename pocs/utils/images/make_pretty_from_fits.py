import os

import matplotlib
matplotlib.use('Agg')
from matplotlib import pyplot as plt
from warnings import warn

from astropy.io import fits
from astropy.wcs import WCS
from astropy.visualization import (MinMaxInterval, LogStretch, ImageNormalize)

from pocs.utils import current_time
from pocs.utils.config import load_config


def _make_pretty_from_fits(fname, timeout=15, **kwargs):
    config = load_config()

    title = '{} {}'.format(kwargs.get('title', ''), current_time().isot)

    new_filename = fname.replace('.fits', '.jpg')

    data = fits.getdata(fname)

    norm = ImageNormalize(interval=MinMaxInterval(), stretch=LogStretch())

    wcs = False

    """
    try:
        wcs = WCS(fname)
    except:
        wcs = False
    ### Why is this commented out? --> See Pull Request
    """

    if wcs:
        ax = plt.subplot(projection=wcs)

        ax.coords.grid(True, color='white', ls='solid')
        ax.coords[0].set_axislabel('Galactic(?) Longitude')
        ax.coords[1].set_axislabel('Galactic(?) Latitude')

        overlay = ax.get_coords_overlay('fk5') # What does this fk5 mean?
        overlay.grid(color='white', ls='dotted')
        overlay[0].set_axislabel('Right Ascension (J2000)')
        overlay[1].set_axislabel('Declination (J2000)')
    else:
        ax = plt.subplot()

        ax.grid(True, color='white', ls='solid')
        ax.set_xlabel('Pixel x-axis')
        ax.set_ylabel('Pixel y-axis')

    ax.imshow(data, norm=norm, cmap='inferno', origin='lower')

    plt.title(title)
    plt.savefig(new_filename)

    image_dir = config['directories']['images']

    ln_fn = '{}/latest.jpg'.format(image_dir)

    try:
        os.remove(ln_fn)
        os.symlink(new_filename, ln_fn)
    except Exception:
        pass

    return new_filename
