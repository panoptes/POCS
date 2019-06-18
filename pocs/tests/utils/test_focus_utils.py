import os
import pytest

from astropy.io import fits

from panoptes.utils.images import focus as focus_utils


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
