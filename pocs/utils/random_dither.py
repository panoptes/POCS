
# coding: utf-8

# # LOOPING DICE-9

# In[1]:

import numpy as np
import astropy.units as u
from astropy.coordinates import SkyCoord
import itertools
import math
import random
import matplotlib.pyplot as plt

def dither_dice9(ra_dec, pattern_offset, random_offset= 0 * u.arcsec, loop=9, plot=False):
    """Dithering for 9 points
    
    Creates a square of 8 points around the central designated point. Then there is a random selection
    in a small region around the designated points in the dither list such that no point is selected twice,
    to produce a more accurate image.
    
    Args:
        ra_dec (SkyCoord of Object): a RA and DEC created using 'SkyCoord'
        pattern_offset (float): an offset for how far around the point you would like to dither.
        random_offset (float, optional): an offset for the defined small region around the points defined in the dither list. Default is 0*u.arcsec
        loop (int, optional): a loop for how many times you would like to dither with the DICE_9 pattern. Default is 9 loop.
        plot (False, optional): a True or False input to say if user would like to plot coordinates. Default is False (no plot)
    
    Returns:
        All: returns 'SkyCoord' as a list and a plot of coordinate positions
    """
    if not isinstance(pattern_offset, u.Quantity):
        pattern_offset = pattern_offset * u.arcsec
    if not isinstance(random_offset, u.Quantity):
        random_offset = random_offset * u.arcsec
    ra = ra_dec.ra
    dec = ra_dec.dec
    number = math.ceil(loop / 9.0)
    # 0.5*2**0.5 is due to adjacent side in a right angle triangle (cos45)
    pattern_ra = (((0.5 * 2 ** 0.5) * pattern_offset) * 0.5) / (np.cos(dec))
    pattern =((0.5 * 2 ** 0.5) * pattern_offset) * 0.5
    random_ra = (random_offset * 0.5) / (np.cos(dec))
    random_dec = (random_offset * 0.5)
    # Dither
    RA_list = [ra]
    DEC_list = [dec]
    for i in range(number):
        ra1 = ra + (pattern_ra)
        RA_list.append(ra1)
        dec1 = dec + (pattern)
        DEC_list.append(dec1)

        ra2 = ra + (pattern_ra)
        RA_list.append(ra2)
        DEC_list.append(dec)

        ra3 = ra + (pattern_ra)
        RA_list.append(ra3)
        dec3 = dec - (pattern)
        DEC_list.append(dec3)

        RA_list.append(ra)
        dec4 = dec - (pattern)
        DEC_list.append(dec4)

        ra5 = ra - (pattern_ra)
        RA_list.append(ra5)
        dec5 = dec - (pattern)
        DEC_list.append(dec5)

        ra6 = ra - (pattern_ra)
        RA_list.append(ra6)
        DEC_list.append(dec)

        ra7 = ra - (pattern_ra)
        RA_list.append(ra7)
        dec7 = dec + (pattern)
        DEC_list.append(dec7)

        RA_list.append(ra)
        dec8 = dec + (pattern)
        DEC_list.append(dec8)

        RA_list.append(ra)
        DEC_list.append(dec)

    RA_final_list = RA_list[:loop]
    DEC_final_list = DEC_list[:loop]
    # Random
    LISTra = []
    LISTdec = []
    for i in range(0, len(RA_final_list)):
        RA_offset = random.uniform(RA_final_list[i] - (random_ra), RA_final_list[i] + (random_ra))
        LISTra.append(RA_offset)
        DEC_offset = random.uniform(DEC_final_list[i] - (random_dec), DEC_final_list[i] + (random_dec))
        LISTdec.append(DEC_offset)
    All = SkyCoord(LISTra, LISTdec)
    if plot is True:
        plt.plot(All.ra, All.dec, 'c-s')
        plt.ylabel('Declination [deg]')
        plt.xlabel('Right Ascension [deg]')
        plt.show()
    return All


# # LOOPING DICE-5

# In[2]:

def dither_dice5(ra_dec, pattern_offset, random_offset= 0 * u.arcsec, loop=5, plot=False):
    """Dithering for 5 points
    
    Creates a square of 4 points around the central designated point. Then there is a random selection
    in a small region around the designated points in the dither list such that no point is selected twice,
    to produce a more accurate image.
    
    Args:
        ra_dec (SkyCoord of Object): a RA and DEC created using 'SkyCoord'
        pattern_offset (float): an offset for how far around the point you would like to dither.
        random_offset (float, optional): an offset for the defined small region around the points defined in the dither list. Default is 0*u.arcsec
        loop (int, optional): a loop for how many times you would like to dither with the DICE_5 pattern. Default is 5 loop.
        plot (False, optional): a True or False input to say if user would like to plot coordinates. Default is False (no plot)
    
    Returns:
        All: returns 'SkyCoord' as a list and a plot of coordinate positions
    """
    if not isinstance(pattern_offset, u.Quantity):
        pattern_offset = pattern_offset * u.arcsec
    if not isinstance(random_offset, u.Quantity):
        random_offset = random_offset * u.arcsec
    ra = ra_dec.ra
    dec = ra_dec.dec
    number = math.ceil(loop / 5.0)
    # 0.5*2**0.5 is due to adjacent side in a right angle triangle (cos45)
    pattern_ra = (((0.5 * 2 ** 0.5) * pattern_offset) * 0.5) / (np.cos(dec))
    pattern =((0.5 * 2 ** 0.5) * pattern_offset) * 0.5
    random_ra = (random_offset * 0.5) / (np.cos(dec))
    random_dec = (random_offset * 0.5)
    # Dither
    RA_list = [ra]
    DEC_list = [dec]
    for i in range(number):
        ra1 = ra + (pattern_ra)
        RA_list.append(ra1)
        dec1 = dec + (pattern)
        DEC_list.append(dec1)

        ra2 = ra + (pattern_ra)
        RA_list.append(ra2)
        dec2 = dec - (pattern)
        DEC_list.append(dec2)

        ra3 = ra - (pattern_ra)
        RA_list.append(ra3)
        dec3 = dec - (pattern)
        DEC_list.append(dec3)

        ra4 = ra - (pattern_ra)
        RA_list.append(ra4)
        dec4 = dec + (pattern)
        DEC_list.append(dec4)

        RA_list.append(ra)
        DEC_list.append(dec)

    RA_final_list = RA_list[:loop]
    DEC_final_list = DEC_list[:loop]
    # Random
    LISTra = []
    LISTdec = []
    for i in range(0, len(RA_final_list)):
        RA_offset = random.uniform(RA_final_list[i] - (random_ra), RA_final_list[i] + (random_ra))
        LISTra.append(RA_offset)
        DEC_offset = random.uniform(DEC_final_list[i] - (random_dec), DEC_final_list[i] + (random_dec))
        LISTdec.append(DEC_offset)
    All = SkyCoord(LISTra, LISTdec)
    if plot is True:
        plt.plot(All.ra, All.dec, 'c-s')
        plt.ylabel('Declination [deg]')
        plt.xlabel('Right Ascension [deg]')
        plt.show()
    return All

