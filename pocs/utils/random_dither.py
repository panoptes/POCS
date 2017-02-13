
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
    if not isinstance(pattern_offset, u.Quantity):
        pattern_offset= pattern_offset * u.arcsec
    if not isinstance(random_offset, u.Quantity):
        random_offset=random_offset * u.arcsec
    ra=ra_dec.ra
    dec=ra_dec.dec
    number=math.ceil(loop/9.0)
    big_ra=(((0.5*2**0.5)*pattern_offset)*0.5)/(np.cos(dec))  #0.5*2**0.5 is due to adjacent side in a right angle triangle (cos45)
    big=((0.5*2**0.5)*pattern_offset)*0.5
    small_ra= (random_offset*0.5)/(np.cos(dec))
    small= (random_offset*0.5)
    """Dither"""
    RA_list=[ra]
    DEC_list=[dec]
    for i in range(number):
        ra1=ra+(big_ra)
        RA_list.append(ra1)
        dec1=dec+(big)
        DEC_list.append(dec1)
        
        ra2=ra+(big_ra)
        RA_list.append(ra2)
        DEC_list.append(dec)
        
        ra3=ra+(big_ra)
        RA_list.append(ra3)
        dec3=dec-(big)
        DEC_list.append(dec3)
        
        RA_list.append(ra)
        dec4=dec-(big)
        DEC_list.append(dec4)
        
        ra5=ra-(big_ra)
        RA_list.append(ra5)
        dec5=dec-(big)
        DEC_list.append(dec5)
        
        ra6=ra-(big_ra)
        RA_list.append(ra6)
        DEC_list.append(dec)
        
        ra7=ra-(big_ra)
        RA_list.append(ra7)
        dec7=dec+(big)
        DEC_list.append(dec7)
        
        RA_list.append(ra)
        dec8=dec+(big)
        DEC_list.append(dec8)
        
        
        RA_list.append(ra)
        DEC_list.append(dec)
        
    
    
    RA_final_list=RA_list[:loop]
    DEC_final_list=DEC_list[:loop]
    """Random"""
    LISTra=[]
    LISTdec=[]
    for i in range(0,len(RA_final_list)):
        RA_offset=random.uniform(RA_final_list[i]-(small_ra),RA_final_list[i]+(small_ra))
        LISTra.append(RA_offset)
        DEC_offset=random.uniform(DEC_final_list[i]-(small),DEC_final_list[i]+(small))
        LISTdec.append(DEC_offset)
    All=SkyCoord(LISTra,LISTdec)
    if plot == True:
        plt.plot(All.ra, All.dec,'c-s')
        plt.ylabel('Declination [deg]')
        plt.xlabel('Right Ascension [deg]')
        plt.show()
    return All


# # LOOPING DICE-5

# In[2]:

import numpy as np
import astropy.units as u
from astropy.coordinates import SkyCoord
import math
import random
import itertools
import matplotlib.pyplot as plt


def dither_dice5(ra_dec, pattern_offset,random_offset=0*u.arcsec, loop=5, plot=False):
    if not isinstance(pattern_offset,u.Quantity):
        pattern_offset=pattern_offset*u.arcsec
    if not isinstance(random_offset,u.Quantity):
        random_offset=random_offset*u.arcsec
    ra=ra_dec.ra
    dec=ra_dec.dec
    number=math.ceil(loop/9.0)
    big_ra=(((0.5*2**0.5)*pattern_offset)*0.5)/(np.cos(dec))  #0.5*2**0.5 is due to adjacent side in a right angle triangle (cos45)
    big=((0.5*2**0.5)*pattern_offset)*0.5
    small_ra= (random_offset*0.5)/(np.cos(dec))
    small= (random_offset*0.5)
    """Dither"""
    RA_list=[ra]
    DEC_list=[dec]
    for i in range(number):
        ra1=ra+(big_ra)
        RA_list.append(ra1)
        dec1=dec+(big)
        DEC_list.append(dec1)
        
        ra2=ra+(big_ra)
        RA_list.append(ra2)
        dec2=dec-(big)
        DEC_list.append(dec2)
        
        ra3=ra-(big_ra)
        RA_list.append(ra3)
        dec3=dec-(big)
        DEC_list.append(dec3)
        
        ra4=ra-(big_ra)
        RA_list.append(ra4)
        dec4=dec+(big)
        DEC_list.append(dec4)
        
        RA_list.append(ra)
        DEC_list.append(dec)
        
    
    RA_final_list=RA_list[:loop]
    DEC_final_list=DEC_list[:loop]
    """Random"""
    LISTra=[]
    LISTdec=[]
    for i in range(0,len(RA_final_list)):
        RA_offset=random.uniform(RA_final_list[i]-(small_ra),RA_final_list[i]+(small_ra))
        LISTra.append(RA_offset)
        DEC_offset=random.uniform(DEC_final_list[i]-(small),DEC_final_list[i]+(small))
        LISTdec.append(DEC_offset)
    All=SkyCoord(LISTra,LISTdec)
    if plot == True:
        plt.plot(All.ra, All.dec,'c-s')
        plt.ylabel('Declination [deg]')
        plt.xlabel('Right Ascension [deg]')
        plt.show()
    return All

