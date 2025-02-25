import numpy as np
from astropy.nddata import Cutout2D
from astropy.visualization import SqrtStretch
from astropy.visualization.mpl_normalize import ImageNormalize
from astropy.wcs import WCS
from matplotlib import pyplot as plt
from panoptes.utils.images.fits import get_solve_field, get_solve_field, getdata
from skimage.feature import canny
from skimage.transform import hough_circle, hough_circle_peaks


def analyze_polar_rotation(pole_fn):
    get_solve_field(pole_fn)

    wcs = WCS(pole_fn)

    pole_cx, pole_cy = wcs.all_world2pix(360, 90, 1)

    return pole_cx, pole_cy


def analyze_ra_rotation(rotate_fn):
    d0 = getdata(rotate_fn)  # - 2048

    # Get center
    position = (d0.shape[1] // 2, d0.shape[0] // 2)
    size = (1500, 1500)
    d1 = Cutout2D(d0, position, size)

    d1.data = d1.data / d1.data.max()

    # Get edges for rotation
    rotate_edges = canny(d1.data, sigma=1.0)

    rotate_hough_radii = np.arange(100, 500, 50)
    rotate_hough_res = hough_circle(rotate_edges, rotate_hough_radii)
    rotate_accums, rotate_cx, rotate_cy, rotate_radii = hough_circle_peaks(
        rotate_hough_res, rotate_hough_radii, total_num_peaks=1
        )

    return d1.to_original_position((rotate_cx[-1], rotate_cy[-1]))


def plot_center(pole_fn, rotate_fn, pole_center, rotate_center, plot_fn=None):

    d0 = getdata(pole_fn) - 2048.
    d1 = getdata(rotate_fn) - 2048.

    d0 /= d0.max()
    d1 /= d1.max()

    pole_cx, pole_cy = pole_center
    rotate_cx, rotate_cy = rotate_center

    fig, ax = plt.subplots(ncols=1, nrows=1, figsize=(20, 18))

    ax.scatter(pole_cx, pole_cy, color='r', marker='x', lw=5)
    ax.scatter(rotate_cx, rotate_cy, color='r', marker='x', lw=5)

    norm = ImageNormalize(stretch=SqrtStretch())

    ax.imshow(d0 + d1, cmap='Greys_r', norm=norm)
    ax.arrow(rotate_cx, rotate_cy, pole_cx - rotate_cx, pole_cy - rotate_cy, fc='r', ec='r')

    if plot_fn is not None:
        fig.savefig(plot_fn)

    return fig
