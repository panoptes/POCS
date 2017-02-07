import astropy.units as u
from astropy.coordinates import SkyCoord
import math
import itertools

"""ra='13 37 00'
dec='-29 51 56.74'
ra_dec=SkyCoord('%s %s'%(ra, dec), unit=(u.hourangle,u.deg))
offset=0.5*u.deg
loop=13
"""


def dither_dice9(ra_dec, offset=30 * u.arcsec, loop=5):
    if not isinstance(offset, u.Quantity):
        offset = offset * u.arcsec
    """ra_dec=SkyCoord('%s %s'%(ra, dec), unit=(u.hourangle,u.deg))"""
    ra = ra_dec.ra
    dec = ra_dec.dec
    number = math.ceil(loop / 9.0)

    RA_list = [ra]
    DEC_list = [dec]
    for _ in itertools.repeat(None, number):
        ra1 = ra + ((0.5 * 2**0.5) * offset)  # 0.5*2**0.5 is due to adjacent side in a right angle triangle (cos45)
        RA_list.append(ra1)
        dec1 = dec + ((0.5 * 2**0.5) * offset)
        DEC_list.append(dec1)

        ra2 = ra + ((0.5 * 2**0.5) * offset)
        RA_list.append(ra2)
        DEC_list.append(dec)

        ra3 = ra + ((0.5 * 2**0.5) * offset)
        RA_list.append(ra3)
        dec3 = dec - ((0.5 * 2**0.5) * offset)
        DEC_list.append(dec3)

        RA_list.append(ra)
        dec4 = dec - ((0.5 * 2**0.5) * offset)
        DEC_list.append(dec4)

        ra5 = ra - ((0.5 * 2**0.5) * offset)
        RA_list.append(ra5)
        dec5 = dec - ((0.5 * 2**0.5) * offset)
        DEC_list.append(dec5)

        ra6 = ra - ((0.5 * 2**0.5) * offset)
        RA_list.append(ra6)
        DEC_list.append(dec)

        ra7 = ra - ((0.5 * 2**0.5) * offset)
        RA_list.append(ra7)
        dec7 = dec + ((0.5 * 2**0.5) * offset)
        DEC_list.append(dec7)

        RA_list.append(ra)
        dec8 = dec + ((0.5 * 2**0.5) * offset)
        DEC_list.append(dec8)

        RA_list.append(ra)
        DEC_list.append(dec)

    RA_final_list = RA_list[:loop]
    DEC_final_list = DEC_list[:loop]
    All = SkyCoord(RA_final_list, DEC_final_list)
    return All

"""All9=dither_dice9(ra_dec,offset,loop)"""

def dither_dice5(ra_dec, offset=30*u.arcsec, loop=5):
    if not isinstance(offset,u.Quantity):
        offset=offset*u.arcsec
    """ra_dec=SkyCoord('%s %s'%(ra, dec), unit=(u.hourangle,u.deg))"""
    ra=ra_dec.ra
    dec=ra_dec.dec
    number=math.ceil(loop/5.0)
    
    RA_list=[ra]
    DEC_list=[dec]
    for _ in itertools.repeat(None, number):
        ra1=ra+((0.5*2**0.5)*offset) #0.5*2**0.5 is due to adjacent side in a right angle triangle (cos45)
        RA_list.append(ra1)
        dec1=dec+((0.5*2**0.5)*offset)
        DEC_list.append(dec1)
        
        ra2=ra+((0.5*2**0.5)*offset)
        RA_list.append(ra2)
        dec2=dec-((0.5*2**0.5)*offset)
        DEC_list.append(dec2)
        
        ra3=ra-((0.5*2**0.5)*offset)
        RA_list.append(ra3)
        dec3=dec-((0.5*2**0.5)*offset)
        DEC_list.append(dec3)
        
        ra4=ra-((0.5*2**0.5)*offset)
        RA_list.append(ra4)
        dec4=dec+((0.5*2**0.5)*offset)
        DEC_list.append(dec4)
        
        RA_list.append(ra)
        DEC_list.append(dec)
        
    
    RA_final_list=RA_list[:loop]
    DEC_final_list=DEC_list[:loop]
    All=SkyCoord(RA_final_list,DEC_final_list)
    return All

"""All5=dither_dice5(ra_dec,offset,loop)"""

def dither_random(dice_list,offset,loop=1):
    if not isinstance(offset,u.Quantity):
        offset=offset*u.arcsec
    if loop>1:
        ra=dice_list.ra
        dec=dice_list.dec
        RA=[]
        DEC=[]
        for _ in itertools.repeat(None, loop):
            offset_ra=random.uniform(ra-(offset*0.5),ra+(offset*0.5))
            RA.append(offset_ra)
            offset_dec=random.uniform(dec-(offset*0.5),dec+(offset*0.5))
            DEC.append(offset_dec)
    else:
        #RA=[dice_list[0].ra]
        #DEC=[dice_list[0].dec]
        RA=random.uniform(dice_list.ra-(offset*0.5),dice_list.ra+(offset*0.5))
        DEC=random.uniform(dice_list.dec-(offset*0.5),dice_list.dec+(offset*0.5))
        

    All=SkyCoord(RA,DEC)
    return All

"""All=dither_random(dice_list,offset)"""
