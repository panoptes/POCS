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
from rich import print
from skimage.feature import canny
from skimage.transform import hough_circle, hough_circle_peaks


def get_celestial_center(pole_fn: Path | str, **kwargs):
    """Analyze the polar rotation image to get the center of the pole.

    Args:
        pole_fn (Path | str): FITS file of polar center
    Returns:
        tuple(int): Polar center XY coordinates
    """
    if isinstance(pole_fn, Path):
        pole_fn = pole_fn.as_posix()

    get_solve_field(pole_fn, **kwargs)

    wcs = WCS(pole_fn)

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
        if not isinstance(fits_fn, Path):
            fits_fn = Path(fits_fn)

        if position == 'home':
            print(f"Processing polar rotation image: {fits_fn}")
            pole_center_x, pole_center_y, pix_scale = get_celestial_center(fits_fn)
            pole_center = (float(pole_center_x), float(pole_center_y))
        else:
            try:
                print(f"Processing RA rotation image: {fits_fn}")
                solve_info = get_solve_field(fits_fn.as_posix())
            except PanError:
                print(f"Unable to solve image {fits_fn}")
                continue
            else:
                # Get the pixel coordinates of Polaris in the image.
                wcs = WCS(fits_fn.as_posix())
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
