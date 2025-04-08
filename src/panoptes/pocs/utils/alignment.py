from pathlib import Path

import numpy as np
from astropy.coordinates import SkyCoord
from astropy.nddata import Cutout2D
from astropy.visualization import SqrtStretch
from astropy.visualization.mpl_normalize import ImageNormalize
from astropy.wcs import WCS
from matplotlib import pyplot as plt
from panoptes.utils.error import PanError
from panoptes.utils.images.fits import get_solve_field, get_wcsinfo, getdata
from skimage.feature import canny
from skimage.transform import hough_circle, hough_circle_peaks

from panoptes.pocs.utils.cli.run import find_circle_params


def get_celestial_center(pole_fn: Path | str, **kwargs):
    """Analyze the polar rotation image to get the center of the pole.

    Args:
        pole_fn (Path | str): FITS file of polar center
    Returns:
        tuple(int): Polar center XY coordinates
    """
    get_solve_field(pole_fn, **kwargs)

    wcs = WCS(pole_fn.as_posix())

    pole_cx, pole_cy = wcs.all_world2pix(360, 90, 1)

    wcsinfo = get_wcsinfo(pole_fn)
    pixscale = None
    if wcsinfo is not None:
        pixscale = wcsinfo['pixscale'].value

    return pole_cx, pole_cy, pixscale


def analyze_ra_rotation(rotate_fn: Path | str):
    """Analyze the RA rotation image to get the center of rotation.

    Args:
        rotate_fn (Path | str): FITS file of RA rotation image
    Returns:
        tuple(int): RA axis center of rotation XY coordinates
    """
    d0 = getdata(rotate_fn.as_posix())

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


def process_quick_alignment(files: dict[str, Path]) -> tuple[
    tuple[float, float], tuple[float, float], float, float, float]:
    """Process the quick alignment of polar rotation and RA rotation images.

    Args:
        files (dict[str, Path]): Dictionary of image positions and their FITS file paths.

    Returns:
        tuple: Polar center coordinates, RA rotation center coordinates, dx, dy, pixel scale
    """
    # Get coordinates for Polaris in each of the images.
    polaris = SkyCoord.from_name('Polaris')

    points = list()
    pole_center = None
    pix_scale = None
    # Find the xy-coords of Polaris in each of the images using the wcs.
    for position, fits_fn in files.items():
        if position == 'home':
            print(f"Processing polar rotation image: {fits_fn}")
            pole_center_x, pole_center_y, pix_scale = get_celestial_center(fits_fn)
            pole_center = (float(pole_center_x), float(pole_center_y))
        else:
            try:
                print(f"Processing RA rotation image: {fits_fn}")
                wcs = get_solve_field(fits_fn.as_posix())
            except PanError:
                print(f"Unable to solve image {fits_fn}")
                continue
            else:
                # Get the pixel coordinates of Polaris in the image.
                x, y = wcs.all_world2pix(polaris.ra.deg, polaris.dec.deg, 1)
                points.append((x, y))

    # Find the circle that best fits the points.
    h, k, R = find_circle_params(points)
    rotate_center = (h, k)

    dx = None
    dy = None

    # Get the distance from the center of the circle to the center of celestial pole.
    if pole_center is not None:
        dx = pole_center[0] - rotate_center[0]
        dy = pole_center[1] - rotate_center[1]

    # Convert deltas to degrees.
    if pix_scale is not None:
        dx = dx * pix_scale / 3600
        dy = dy * pix_scale / 3600

    return pole_center, rotate_center, dx, dy, pix_scale


def plot_center(pole_fn, rotate_fn, pole_center, rotate_center):
    """ Overlay the celestial pole and RA rotation axis images.

    Args:
        pole_fn (str): FITS file of polar center
        rotate_fn (str): FITS file of RA rotation image
        pole_center (tuple(int)): Polar center XY coordinates
        rotate_center (tuple(int)): RA axis center of rotation XY coordinates
    Returns:
        matplotlib.Figure: Plotted image
    """
    d0 = getdata(pole_fn) - 0.  # Easy cast to float
    d1 = getdata(rotate_fn) - 0.  # Easy cast to float

    d0 /= d0.max()
    d1 /= d1.max()

    pole_cx, pole_cy = pole_center
    rotate_cx, rotate_cy = rotate_center

    d_x = pole_center[0] - rotate_center[0]
    d_y = pole_center[1] - rotate_center[1]

    fig, ax = plt.subplots(ncols=1, nrows=1, figsize=(20, 14))

    # Show rotation center in red
    ax.scatter(rotate_cx, rotate_cy, color='r', marker='x', lw=5)

    # Show polar center in green
    ax.scatter(pole_cx, pole_cy, color='g', marker='x', lw=5)

    # Show both images in background
    norm = ImageNormalize(stretch=SqrtStretch())
    ax.imshow(d0 + d1, cmap='Greys_r', norm=norm, origin='lower')

    # Show an arrow
    delta_cy = pole_cy - rotate_cy
    delta_cx = pole_cx - rotate_cx
    if (np.abs(delta_cy) > 25) or (np.abs(delta_cx) > 25):
        ax.arrow(
            rotate_cx,
            rotate_cy,
            delta_cx,
            delta_cy,
            fc='r',
            ec='r',
            width=20,
            length_includes_head=True
        )

    ax.set_title(f"dx: {d_x:0.2f} pix   dy: {d_y:0.2f} pix")

    return fig
