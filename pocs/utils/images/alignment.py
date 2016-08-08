import os
import numpy as np
from astropy import units as u
# from astropy.coordinates import SkyCoord
from astropy import wcs
from astropy.io import fits
from skimage.feature import register_translation

from .io import cr2_to_fits

def compute_offset(imreffile, imfile, wcsfile=None, rotation=True, output='pix'):
    assert output in ['pix', 'arcsec']
    assert os.path.splitext(imfile)[1].lower() == '.cr2', "expected .cr2 extension"
    assert os.path.splitext(imreffile)[1].lower() == '.cr2', "expected .cr2 extension"
    imfile_fits = cr2_to_fits(imfile)
    imreffile_fits = cr2_to_fits(imreffile)
    im_hdul = fits.open(imfile_fits)
    imref_hdul = fits.open(imreffile_fits)
    offset_pix = compute_subframe_offset(im_hdul[0].data, imref_hdul[0].data,
                                         rotation=rotation)
    if output == 'pix':
        return offset_pix
    elif output == 'arcsec':
        if wcsfile:
            try:
                hdul = fits.open(wcsfile)
                w = wcs.WCS(hdul[0].header)
            except:
                print('No WCS Found')
                return pixoffset
        else:
            try:
                w = wcs.WCS(imref_hdul[0].header)
                assert w.is_celestial
            except:
                print('No WCS Found')
                return pixoffset

        deltapix = [offset_pix[0].to(u.pixel).value,
                    offset_pix[1].to(u.pixel).value]
        offset_deg = w.pixel_scale_matrix.dot(deltapix)
        offset = u.Quantity([(offset_deg[0]*u.degree).to(u.arcsecond),
                             (offset_deg[1]*u.degree).to(u.arcsecond),
                             offset_pix[2].to(u.arcsecond),
                             ])
        return offset



def compute_subframe_offset(im, imref, rotation=True):
    assert im.shape == imref.shape
    ny, nx = im.shape
    
    size = 200

    # regions is x0, x1, y0, y1, xcen, ycen
    regions = {'center': (int(nx/2-size/2), int(nx/2+size/2),
                          int(ny/2-size/2), int(ny/2+size/2),
                          int(nx/2), int(ny/2))}
    if rotation is True:
        regions['upper right'] = (nx-size, nx,
                                  ny-size, ny,
                                  int(nx-size/2), int(ny-size/2))
        regions['upper left'] = (0, size,
                                 ny-size, ny,
                                 int(size/2), int(ny-size/2))
        regions['lower right'] = (nx-size, nx,
                                  0, size,
                                  int(nx-size/2), int(size/2))
        regions['lower left'] = (0, size,
                                 0, size,
                                 int(size/2), int(size/2))

    offsets = {'center': None,
               'upper right': None,
               'upper left': None,
               'lower right': None,
               'lower left': None}
    for region in regions.keys():
        imarr = im[regions[region][2]:regions[region][3], regions[region][0]:regions[region][1]]
        imrefarr = imref[regions[region][2]:regions[region][3], regions[region][0]:regions[region][1]]
        shifts, err, hasediff = register_translation(imrefarr, imarr, upsample_factor=10)
        offsets[region] = shifts

    angles = []
    for region in regions.keys():
        if region != 'center':
            offsets[region] -= offsets['center']
            relpos = (regions[region][4]-regions['center'][4], regions[region][5]-regions['center'][5])
            theta1 = np.arctan(relpos[1]/relpos[0])
            theta2 = np.arctan((relpos[1]+offsets[region][1])/(relpos[0]+offsets[region][0]))
            angles.append(theta2 - theta1)
    angle = np.mean(angles)
    result = (offsets['center'][0]*u.pix,
              offsets['center'][1]*u.pix,
              (angle*u.radian).to(u.degree))
    return result

