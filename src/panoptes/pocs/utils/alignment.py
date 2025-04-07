from pathlib import Path

import numpy as np
from astropy import units as u
from astropy.nddata import Cutout2D
from astropy.visualization import ImageNormalize, LogStretch
from astropy.wcs import WCS
from matplotlib.figure import Figure
from panoptes.utils.images.fits import get_solve_field, get_wcsinfo, getdata
from panoptes.utils.images.plot import add_colorbar
from skimage.feature import canny
from skimage.transform import hough_circle, hough_circle_peaks


def analyze_polar_rotation(pole_fn: Path | str, **kwargs) -> tuple[float, float, float]:
    """Analyze the polar rotation image to get the center of the pole.

    Args:
        pole_fn (Path | str): FITS file of polar center.
    Returns:
        tuple(float, float, float): Polar center XY coordinates and pixel scale.
    """
    if isinstance(pole_fn, str):
        pole_fn = Path(pole_fn)

    wcs = WCS(pole_fn.as_posix())

    if wcs.is_celestial is False:
        get_solve_field(pole_fn, **kwargs)
        wcs = WCS(pole_fn.as_posix())

    wcsinfo = get_wcsinfo(pole_fn.as_posix())
    pixel_scale = wcsinfo['pixscale']

    pole_cx, pole_cy = wcs.all_world2pix(360, 90, 1)

    return pole_cx, pole_cy, float(pixel_scale.to_value())


def analyze_ra_rotation(rotate_fn: Path | str):
    """Analyze the RA rotation image to get the center of rotation.

    Args:
        rotate_fn (Path | str): FITS file of RA rotation image
    Returns:
        tuple(int): RA axis center of rotation XY coordinates
    """
    if isinstance(rotate_fn, str):
        rotate_fn = Path(rotate_fn)
    d0 = getdata(rotate_fn.as_posix())

    # Get center
    position = (d0.shape[1] // 2, d0.shape[0] // 2)
    size = (2000, 2000)
    d1 = Cutout2D(d0, position, size)

    d1.data = d1.data - np.median(d1.data)
    d1.data[d1.data < 0] = 0
    # d1.data = d1.data / d1.data.max()
    # d0 = sigma_clip(d0)

    # Get edges for rotation
    rotate_edges = canny(d1.data, sigma=1)

    rotate_hough_radii = np.arange(10, 500, 50)
    rotate_hough_res = hough_circle(rotate_edges, rotate_hough_radii)
    rotate_accums, rotate_cx, rotate_cy, rotate_radii = hough_circle_peaks(
        rotate_hough_res, rotate_hough_radii, total_num_peaks=1
    )

    return d1.to_original_position((rotate_cx[-1], rotate_cy[-1]))
    # return rotate_cx[-1], rotate_cy[-1]


def plot_center(pole_fn: Path,
                rotate_fn: Path,
                pole_center: tuple[float, float],
                rotate_center: tuple[float, float],
                pixel_scale: float
                ):
    """ Overlay the celestial pole and RA rotation axis images.

    Args:
        pole_fn (Path): FITS file of polar center.
        rotate_fn (Path): FITS file of RA rotation image.
        pole_center (tuple(int)): Polar center XY coordinates.
        rotate_center (tuple(int)): RA axis center of rotation XY coordinates.
        pixel_scale (float): Pixel scale in arcseconds per pixel.
    Returns:
        matplotlib.Figure: Plotted image
    """
    pole_data = getdata(pole_fn.as_posix()) - 0.  # Easy cast to float
    rotate_data = getdata(rotate_fn.as_posix()) - 0.  # Easy cast to float

    pole_data -= np.median(pole_data)
    rotate_data -= np.median(rotate_data)

    # pole_data /= pole_data.max()
    # rotate_data /= rotate_data.max()

    pole_cx, pole_cy = pole_center * u.pixel
    rotate_cx, rotate_cy = rotate_center * u.pixel

    delta_cx = pole_cx - rotate_cx
    delta_cy = pole_cy - rotate_cy

    pixel_scale = pixel_scale * u.arcsec / u.pixel

    # Convert pixel change to degrees.
    dx_deg = (delta_cx * pixel_scale).to(u.degree).to_value()
    dy_deg = (delta_cy * pixel_scale).to(u.degree).to_value()

    wcs = WCS(pole_fn.as_posix())

    # Create figure
    fig = Figure(figsize=(20, 14), layout='constrained')
    ax = fig.add_subplot(1, 1, 1, projection=wcs)

    alpha = 0.45
    number_ticks = 10
    clip_percent = 99.5

    ax.grid(True, color='blue', ls='-', alpha=alpha)

    ra_axis = ax.coords['ra']
    ra_axis.set_axislabel('Right Ascension')
    ra_axis.set_major_formatter('hh:mm')
    ra_axis.set_ticks(number=number_ticks, color='cyan')
    # ra_axis.set_ticklabel(color='white', exclude_overlapping=True)

    dec_axis = ax.coords['dec']
    dec_axis.set_axislabel('Declination')
    dec_axis.set_major_formatter('dd:mm')
    dec_axis.set_ticks(number=number_ticks, color='cyan')
    # dec_axis.set_ticklabel(color='white', exclude_overlapping=True)

    # Show rotation center in red
    # ax.scatter(rotate_cx, rotate_cy, fc='r', marker='o', s=50, label='Rotation Center')

    # Show polar center in green
    ax.scatter(pole_cx, pole_cy, fc='g', marker='o', s=50, label='Pole Center')

    # Show both images in background
    norm = ImageNormalize(stretch=LogStretch())

    # Replace negative values with zero.
    pole_data[pole_data < 0] = 0
    rotate_data[rotate_data < 0] = 0

    # ax.imshow(pole_data, cmap='Greys_r', origin='lower')
    im = ax.imshow(rotate_data + pole_data, cmap='Greys_r', norm=norm)
    add_colorbar(im)

    ax.legend()

    # Show an arrow
    rotate_cx = rotate_cx.to_value()
    rotate_cy = rotate_cy.to_value()
    delta_cx = delta_cx.to_value()
    delta_cy = delta_cy.to_value()
    # if (np.abs(delta_cy) > 25) or (np.abs(delta_cx) > 25):
    #     ax.arrow(
    #         rotate_cx,
    #         rotate_cy,
    #         delta_cx,
    #         delta_cy,
    #         fc='r',
    #         ec='r',
    #         width=15,
    #         length_includes_head=True,
    #     )

    # Show the pixel and degree deltas in the title.
    fig.suptitle('',
        # f"dx = {delta_cx:10.1f} pix, {dx_deg:10.1f} deg \n"
        # f"dy = {delta_cy:10.1f} pix, {dy_deg:10.1f} deg",
        y=0.95,
        fontsize=20,
        color='yellow',
    )

    return fig


def find_circle_params(points):
    """
    Calculates the center (h, k) and radius (R) of a circle given a list of points.

    Args:
        points: A list of tuples, where each tuple represents a point (x, y).
                The list must contain at least three points.

    Returns:
        A tuple (h, k, R) representing the center and radius of the circle.
        Returns (None, None, None) if the input is invalid or no circle can be found.
    """
    if not isinstance(points, list) or len(points) < 3:
        print("Error: Input must be a list of at least three points.")
        return None, None, None

    # Extract x and y coordinates
    x_coords = [p[0] for p in points]
    y_coords = [p[1] for p in points]

    # Construct the matrix A and vector b for the system of equations
    A = np.array(
        [
            [x_coords[0], y_coords[0], 1],
            [x_coords[1], y_coords[1], 1],
            [x_coords[2], y_coords[2], 1]
        ]
    )
    b = np.array(
        [
            -(x_coords[0] ** 2 + y_coords[0] ** 2),
            -(x_coords[1] ** 2 + y_coords[1] ** 2),
            -(x_coords[2] ** 2 + y_coords[2] ** 2)
        ]
    )

    # Solve the system of equations Ax = b for the coefficients D, E, and F
    try:
        x = np.linalg.solve(A, b)
        D, E, F = x
    except np.linalg.LinAlgError:
        print("Error: Points are collinear or do not form a unique circle.")
        return None, None, None

    # Calculate the center (h, k) and radius (R)
    h = -D / 2
    k = -E / 2
    R = np.sqrt(h ** 2 + k ** 2 - F)

    return h, k, R
