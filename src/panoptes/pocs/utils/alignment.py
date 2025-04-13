import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from astropy.coordinates import SkyCoord
from astropy.io.fits.verify import VerifyWarning
from astropy.nddata import Cutout2D
from astropy.visualization import LogStretch, SqrtStretch
from astropy.visualization.mpl_normalize import ImageNormalize
from astropy.wcs import WCS
from loguru import Logger
from matplotlib import pyplot as plt
from matplotlib.figure import Figure
from matplotlib.patches import Circle
from panoptes.utils.error import PanError
from panoptes.utils.images import fits
from panoptes.utils.images.fits import get_solve_field, get_wcsinfo, getdata
from rich import print
from skimage.feature import canny
from skimage.transform import hough_circle, hough_circle_peaks

warnings.simplefilter('ignore', category=VerifyWarning)


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


@dataclass
class AlignmentResult:
    pole_center: tuple[float, float]
    rotate_center: tuple[float, float]
    rotate_radius: float
    pix_scale: float
    target_points: dict[str, tuple[float, float]]
    target_name: str
    dx_deg: float
    dy_deg: float

    def __str__(self):
        # Pretty print
        return (f"Celestial Center: {self.pole_center[0]:.2f}, {self.pole_center[1]:.2f}\n"
                f"Rotate Center: {self.rotate_center[0]:.2f}, {self.rotate_center[1]:.2f}\n"
                f"Rotate Radius: {self.rotate_radius:.02f}\n"
                f"Pixel Scale: {self.pix_scale:.02f}\n"
                f"Target Name: {self.target_name}\n"
                f"Target Points: {[(n, (int(p[0]), int(p[1]))) for n, p in self.target_points.items()]}\n"
                f"Delta (degrees): {self.dx_deg:.02f} {self.dy_deg:.02f}\n"
                )


def process_quick_alignment(files: dict[str, Path], target_name: str = 'Polaris', logger: Logger | None = None
                            ) -> AlignmentResult:
    """Process the quick alignment of polar rotation and RA rotation images.

    Args:
        files (dict[str, Path]): Dictionary of image positions and their FITS file paths.
        target_name (str): Name of the target to align to (default: 'Polaris').
        logger (Logger | None): Logger instance for logging messages.

    Returns:
        tuple: Polar center coordinates, RA rotation center coordinates, dx, dy, pixel scale
    """
    # Get coordinates for Polaris in each of the images.
    target = SkyCoord.from_name(target_name)

    points = dict()
    pole_center = None
    pix_scale = None
    # Find the xy-coords of Polaris in each of the images using the wcs.
    for position, fits_fn in files.items():
        if not isinstance(fits_fn, Path):
            fits_fn = Path(fits_fn)

        if position == 'home':
            logger.debug(f"Processing polar rotation image: {fits_fn}")
            pole_center_x, pole_center_y, pix_scale = get_celestial_center(fits_fn)
            pole_center = (float(pole_center_x), float(pole_center_y))
            points[position] = pole_center
        else:
            try:
                logger.debug(f"Processing RA rotation image: {fits_fn}")
                # If it's not already solved it probably needs a longer timeout.
                solve_info = get_solve_field(fits_fn.as_posix(), timeout=90)
            except PanError:
                logger.warning(f"Unable to solve image {fits_fn}")
                continue
            else:
                # Get the pixel coordinates of Polaris in the image.
                wcs = WCS(fits_fn.as_posix())
                x, y = wcs.all_world2pix(target.ra.deg, target.dec.deg, 1)
                points[position] = (x, y)

    # Find the circle that best fits the points.
    h, k, R = find_circle_params(points)
    rotate_center = (h, k)

    if pole_center is None or rotate_center is None:
        logger.warning(f'Unable to determine centers for alignment. {pole_center=} {rotate_center=}')
        raise PanError("Unable to determine centers for alignment.")

    # Get the distance from the center of the circle to the center of celestial pole.
    dx = pole_center[0] - rotate_center[0]
    dy = pole_center[1] - rotate_center[1]

    # Convert deltas to degrees.
    if pix_scale is not None:
        dx = dx * pix_scale / 3600
        dy = dy * pix_scale / 3600

    return AlignmentResult(
        pole_center=pole_center,
        rotate_center=rotate_center,
        rotate_radius=R,
        dx_deg=dx,
        dy_deg=dy,
        pix_scale=pix_scale,
        target_points=points,
        target_name=target_name
    )


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


def find_circle_params(points: dict[str, tuple[float, float]]) -> tuple[float, float, float]:
    """
    Calculates the center (h, k) and radius (R) of a circle given a list of points.

    Args:
        points: A dictionary with keys as position names and values as tuples of (x, y) coordinates.

    Returns:
        A tuple (h, k, R) representing the center and radius of the circle.
        Returns (None, None, None) if the input is invalid or no circle can be found.
    """
    if len(points) < 3:
        print("Error: Input must be a list of at least three points.")
        return None, None, None

    # Extract x and y coordinates
    x_coords = [p[0] for p in points.values()]
    y_coords = [p[1] for p in points.values()]

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
    discriminant = h ** 2 + k ** 2 - F
    if discriminant < 0:
        print("Error: Invalid circle parameters, negative value under square root.")
        return None, None, None
    R = np.sqrt(discriminant)
    return h, k, R


def plot_alignment_diff(cam_name: str, files: dict[str, str | Path], results: AlignmentResult) -> Figure:
    """Plot the difference between the celestial pole and RA rotation images.

    Args:
        cam_name (str): Name of the camera.
        files (dict[str, str | Path]): Dictionary of image positions and their FITS file paths.
        results (AlignmentResult): Results from the alignment process.

    Returns:
        Figure: Matplotlib figure object.
    """
    pole_cx, pole_cy = results.pole_center
    rotate_cx, rotate_cy = results.rotate_center

    data0 = fits.getdata(files['home'])
    wcs0 = fits.getwcs(files['home'])

    # Create figure
    fig = Figure(figsize=(20, 14), layout='constrained')
    ax = fig.add_subplot(1, 1, 1, projection=wcs0)

    alpha = 0.3
    number_ticks = 9

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

    # Show both images in background
    norm = ImageNormalize(stretch=LogStretch())

    # Replace negative values with zero.
    data0[data0 < 0] = 0

    # Get the delta in pixels.
    delta_cx = pole_cx - rotate_cx
    delta_cy = pole_cy - rotate_cy

    # Show the background
    im = ax.imshow(data0, cmap='Greys_r', norm=norm)

    # Show the detected points.
    for pos, (x, y) in results.target_points.items():
        ax.scatter(x, y, marker='o', ec='coral', fc='none', lw=2, label=f"{results.target_name} {pos}")
        ax.annotate(pos, (x, y), c='coral', xytext=(3, 3), textcoords='offset pixels')

    # Show the rotation center.
    ax.scatter(rotate_cx, rotate_cy, marker='*', c='coral', zorder=200, label='Center of mount rotation')

    # Show the rotation circle
    ax.add_patch(
        Circle(
            (results.rotate_center[0], results.rotate_center[1]), results.rotate_radius, color='coral', fill=False,
            alpha=0.5, label='Circle of mount rotation', zorder=200
        )
    )

    # Arrow from rotation center to celestial center.
    move_arrow = None
    if (np.abs(delta_cy) > 25) or (np.abs(delta_cx) > 25):
        move_arrow = ax.arrow(
            rotate_cx,
            rotate_cy,
            delta_cx,
            delta_cy,
            fc='r',
            ec='r',
            width=10,
            length_includes_head=True
        )

    # Arrow for rotation radius.
    ax.arrow(
        results.rotate_center[0], results.rotate_center[1], -results.rotate_radius, 0, color='pink',
        length_includes_head=True, width=10, alpha=0.25
    )

    # Arrow for required mount motion.
    ax.arrow(
        results.rotate_center[0], results.rotate_center[1], delta_cx, delta_cy, color='red', length_includes_head=True,
        width=10, zorder=101
    )

    # Show the celestial center
    ax.scatter(pole_cx, pole_cy, marker='*', c='blue', label='Center of celestial sphere')

    # Get the handles and labels from the existing legend
    handles, labels = ax.get_legend_handles_labels()

    # Add the new handle and label
    if move_arrow is not None:
        handles.append(move_arrow)
        labels.append('Direction to move mount')

        # Call legend() again to update the legend
        ax.legend(handles, labels, loc='upper right')

    title0 = (f'{delta_cx=:10.01f} pix RA ={results.dx_deg:10.02f} deg \n {delta_cy=:10.01f} pix  Dec='
              f'{results.dy_deg:10.02f} deg')
    fig.suptitle(f'{cam_name}\n{title0}', y=0.93)

    return fig
