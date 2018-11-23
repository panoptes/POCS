import numpy as np
import astropy.units as u
from astropy.coordinates import SkyCoord
from astropy.coordinates import SkyOffsetFrame
from astropy.coordinates import ICRS
from astropy.wcs import WCS

from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure

# Pattern for dice 9 3x3 grid (sequence of (RA offset, dec offset) pairs)
dice9 = ((0, 0),
         (0, 1),
         (1, 1),
         (1, 0),
         (1, -1),
         (0, -1),
         (-1, -1),
         (-1, 0),
         (-1, 1))


# Pattern for dice 5 grid (sequence of (RA offset, dec offset) pairs)
dice5 = ((0, 0),
         (1, 1),
         (1, -1),
         (-1, -1),
         (-1, 1))


def get_dither_positions(base_position,
                         n_positions,
                         pattern=None,
                         pattern_offset=30 * u.arcminute,
                         random_offset=None):
    """Create a a dithering pattern for a given position.

    Given a base position creates a SkyCoord list of dithered sky positions,
    applying a dither pattern and/or random dither offsets.

    Args:
        base_position (SkyCoord or compatible): base position for the dither pattern,
            either a SkyCoord or an object that can be converted to one by the SkyCoord
            constructor (e.g. string).
        n_positions (int): number of dithered sky positions to generate.
        pattern (sequence of 2-tuples, optional): sequence of (RA offset, dec offset)
            tuples, in units of the pattern_offset. If given pattern_offset must also
            be specified.
        pattern_offset (Quantity, optional): scale for the dither pattern. Should
            be a Quantity with angular units, if a numeric type is passed instead
            it will be assumed to be in arceconds. If pattern offset is given pattern
            must be given too. Default 30 arcminutes.
        random_offset (Quantity, optional): scale of the random offset to apply
            to both RA and dec. Should be a Quantity with angular units, if numeric
            type passed instead it will be assumed to be in arcseconds.

    Returns:
        SkyCoord: list of n_positions dithered sky positions.

    Raises:
        ValueError: Raised if the `base_position` is not a valid `astropy.coordinates.SkyCoord`.
    """
    if not isinstance(base_position, SkyCoord):
        try:
            base_position = SkyCoord(base_position)
        except ValueError:
            raise ValueError(f"Base position '{base_position}' cannot be converted to a SkyCoord")

    # Use provided pattern if given.
    if pattern:
        if not isinstance(pattern_offset, u.Quantity):
            pattern_offset = pattern_offset * u.arcsec

        # Get n_positions from the pattern
        ra_offsets = [pattern[count % len(pattern)][0] for count in range(n_positions)]
        dec_offsets = [pattern[count % len(pattern)][1] for count in range(n_positions)]

        # Apply offsets to positions
        ra_offsets *= pattern_offset
        dec_offsets *= pattern_offset

    else:
        ra_offsets = np.zeros(n_positions) * u.arcsec
        dec_offsets = np.zeros(n_positions) * u.arcsec

    if random_offset:
        if not isinstance(random_offset, u.Quantity):
            random_offset = random_offset * u.arcsec

        # Apply random offsets
        ra_offsets += np.random.uniform(low=-1, high=+1, size=ra_offsets.shape) * random_offset
        dec_offsets += np.random.uniform(low=-1, high=+1, size=dec_offsets.shape) * random_offset

    offsets = SkyOffsetFrame(lon=ra_offsets, lat=dec_offsets, origin=base_position)
    positions = offsets.transform_to(ICRS)

    dither_coords = SkyCoord(positions)

    return dither_coords


def plot_dither_pattern(dither_positions):
    """Utility function to generate a plot of the dither pattern.

    Args:
        dither_positions (SkyCoord): SkyCoord positions to be plotted as generated from
            `get_dither_positions`.

    Returns:
        `matplotlib.figure.Figure`: The matplotlib plot.
    """
    fig = Figure()
    FigureCanvas(fig)

    base_position = dither_positions[0]

    dummy_wcs = WCS(naxis=2)
    dummy_wcs.wcs.ctype = ['RA---TAN', 'DEC--TAN']
    dummy_wcs.wcs.crval = [base_position.ra.value, base_position.dec.value]
    ax = fig.add_subplot(111, projection=dummy_wcs)

    ax.plot(dither_positions.ra, dither_positions.dec, 'b*-', transform=ax.get_transform('world'))
    ax.plot(base_position.ra.value, base_position.dec.value,
            'rx', transform=ax.get_transform('world'))

    ax.set_aspect('equal', adjustable='datalim')
    ax.coords[0].set_axislabel('Right Ascension')
    ax.coords[0].set_major_formatter('hh:mm')
    ax.coords[1].set_axislabel('Declination')
    ax.coords[1].set_major_formatter('dd:mm')
    ax.grid()

    ax.set_title(base_position.to_string('hmsdms'))

    fig.set_size_inches(8, 8.5)

    return fig
