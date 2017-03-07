
import numpy as np
import astropy.units as u
from astropy.coordinates import SkyCoord, SkyOffsetFrame, ICRS
from astropy.wcs import WCS

import matplotlib
matplotlib.use('AGG')
import matplotlib.pyplot as plt

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


def dither(base_position, n_positions, pattern=None, pattern_offset=None, random_offset=None, plot=False):
    """
    Given a base position creates a SkyCoord list of dithered sky positions, applying a dither pattern and/or
    random dither offsets.

    Args:
         base_position (SkyCoord or compatible): base position for the dither pattern, either a SkyCoord or an object
             that can be converted to one by the SkyCoord constructor (e.g. string)
         n_positions (int): number of dithered sky positions to generate
         pattern (sequence of 2-tuples, optional): sequence of (RA offset, dec offset) tuples, in units of the
             pattern_offset. If given pattern_offset must also be specified.
         pattern_offset (Quantity, optional): scale for the dither pattern. Should be a Quantity with angular
             units, if a numeric type is passed instead it will be assumed to be in arceconds. If pattern offset is
             given pattern must be given too.
         random_offset (Quantity, optional): scale of the random offset to apply to both RA and dec. Should be a
             Quantity with angular units, if numeric type passed instead it will be assumed to be in arcseconds.
         plots (optional, default False): If False no plots will be created, otherwise plots will be generated and
             written to filename `plots`.

    Returns:
        SkyCoord: list of n_positions dithered sky positions
    """
    if not isinstance(base_position, SkyCoord):
        try:
            base_position = SkyCoord(base_position)
        except ValueError:
            raise ValueError("Base position '{}' could not be converted to a SkyCoord object!".format(base_position))

    if pattern:
        if not pattern_offset:
            raise ValueError("`pattern` specified but no `pattern_offset` given!")

        if not isinstance(pattern_offset, u.Quantity):
            pattern_offset = pattern_offset * u.arcsec

        pattern_length = len(pattern)

        RA_offsets = [pattern[count % pattern_length][0] for count in range(n_positions)] * pattern_offset
        dec_offsets = [pattern[count % pattern_length][1] for count in range(n_positions)] * pattern_offset

    else:
        RA_offsets = np.zeros(n_positions) * u.arcsec
        dec_offsets = np.zeros(n_positions) * u.arcsec

    if random_offset:
        if not isinstance(random_offset, u.Quantity):
            random_offset = random_offset * u.arcsec

        RA_offsets += np.random.uniform(low=-1, high=+1, size=RA_offsets.shape) * random_offset
        dec_offsets += np.random.uniform(low=-1, high=+1, size=dec_offsets.shape) * random_offset

    offsets = SkyOffsetFrame(lon=RA_offsets, lat=dec_offsets, origin=base_position)
    positions = offsets.transform_to(ICRS)

    if plot:
        dummy_wcs = WCS(naxis=2)
        dummy_wcs.wcs.ctype = ['RA---TAN', 'DEC--TAN']
        dummy_wcs.wcs.crval = [base_position.ra.value, base_position.dec.value]

        ax = plt.subplot(projection=dummy_wcs)
        ax.plot(positions.ra, positions.dec, 'b*-', transform=ax.get_transform('world'))
        ax.plot([base_position.ra.value], [base_position.dec.value], 'rx', transform=ax.get_transform('world'))
        ax.set_aspect('equal', adjustable='datalim')
        ax.coords[0].set_axislabel('Right Ascension')
        ax.coords[0].set_major_formatter('hh:mm')
        ax.coords[1].set_axislabel('declination')
        ax.coords[1].set_major_formatter('dd:mm')
        ax.grid()
        plt.title('base position: {},\nnumber of positions: {}\npattern offset: {},\nrandom offset: {}'.format(base_position.to_string('hmsdms'),
                                                                                                               n_positions,
                                                                                                               pattern_offset,
                                                                                                               random_offset))
        plt.gcf().set_size_inches(8, 8.5)
        plt.savefig(plot)

    return SkyCoord(positions)
