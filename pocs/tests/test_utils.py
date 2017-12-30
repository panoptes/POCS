import numpy as np
import os
import pytest

from datetime import datetime as dt

from astropy.io import fits

from pocs.utils import current_time
from pocs.utils import images as img_utils
from pocs.utils.images import fits as fits_utils
from pocs.utils.images import focus as focus_utils
from pocs.utils import list_connected_cameras
from pocs.utils import listify
from pocs.utils import load_module
from pocs.utils.error import NotFound


@pytest.fixture
def solved_fits_file(data_dir):
    return '{}/solved.fits'.format(data_dir)


def test_bad_load_module():
    with pytest.raises(NotFound):
        load_module('FOOBAR')


def test_listify():
    assert listify(12) == [12]
    assert listify([1, 2, 3]) == [1, 2, 3]


def test_empty_listify():
    assert listify(None) == []


def test_crop_data():
    ones = np.ones((201, 201))
    assert ones.sum() == 40401.

    cropped01 = img_utils.crop_data(ones, verbose=True)
    assert cropped01.sum() == 40000.

    cropped02 = img_utils.crop_data(ones, verbose=True, box_width=10)
    assert cropped02.sum() == 100.


def test_wcsinfo(solved_fits_file):
    wcsinfo = fits_utils.get_wcsinfo(solved_fits_file)

    assert 'wcs_file' in wcsinfo
    assert wcsinfo['ra_center'].value == 303.206422334


def test_fpack(solved_fits_file):
    info = os.stat(solved_fits_file)
    assert info.st_size > 0.

    compressed = fits_utils.fpack(solved_fits_file, verbose=True)

    assert os.stat(compressed).st_size < info.st_size

    uncompressed = fits_utils.fpack(compressed, unpack=True, verbose=True)
    assert os.stat(uncompressed).st_size == info.st_size


def test_pretty_time():
    t0 = '2016-08-13 10:00:00'
    os.environ['POCSTIME'] = t0

    t1 = current_time(pretty=True)
    assert t1 == t0

    t2 = current_time(flatten=True)
    assert t2 != t0
    assert t2 == '20160813T100000'

    t3 = current_time(datetime=True)
    assert t3 == dt(2016, 8, 13, 10, 0, 0)


def test_list_connected_cameras():
    ports = list_connected_cameras()
    assert isinstance(ports, list)


def test_has_camera_ports():
    ports = list_connected_cameras()
    assert isinstance(ports, list)

    for port in ports:
        assert port.startswith('usb:')


def test_vollath_f4(data_dir):
    data = fits.getdata(os.path.join(data_dir, 'unsolved.fits'))
    data = focus_utils.mask_saturated(data)
    assert focus_utils.vollath_F4(data) == pytest.approx(14667.207897717599)
    assert focus_utils.vollath_F4(data, axis='Y') == pytest.approx(14380.343807477504)
    assert focus_utils.vollath_F4(data, axis='X') == pytest.approx(14954.071987957694)
    with pytest.raises(ValueError):
        focus_utils.vollath_F4(data, axis='Z')


def test_focus_metric_default(data_dir):
    data = fits.getdata(os.path.join(data_dir, 'unsolved.fits'))
    data = focus_utils.mask_saturated(data)
    assert focus_utils.focus_metric(data) == pytest.approx(14667.207897717599)
    assert focus_utils.focus_metric(data, axis='Y') == pytest.approx(14380.343807477504)
    assert focus_utils.focus_metric(data, axis='X') == pytest.approx(14954.071987957694)
    with pytest.raises(ValueError):
        focus_utils.focus_metric(data, axis='Z')


def test_focus_metric_vollath(data_dir):
    data = fits.getdata(os.path.join(data_dir, 'unsolved.fits'))
    data = focus_utils.mask_saturated(data)
    assert focus_utils.focus_metric(
        data, merit_function='vollath_F4') == pytest.approx(14667.207897717599)
    assert focus_utils.focus_metric(
        data,
        merit_function='vollath_F4',
        axis='Y') == pytest.approx(14380.343807477504)
    assert focus_utils.focus_metric(
        data,
        merit_function='vollath_F4',
        axis='X') == pytest.approx(14954.071987957694)
    with pytest.raises(ValueError):
        focus_utils.focus_metric(data, merit_function='vollath_F4', axis='Z')


def test_focus_metric_bad_string(data_dir):
    data = fits.getdata(os.path.join(data_dir, 'unsolved.fits'))
    data = focus_utils.mask_saturated(data)
    with pytest.raises(KeyError):
        focus_utils.focus_metric(data, merit_function='NOTAMERITFUNCTION')
