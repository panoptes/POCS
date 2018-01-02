import os
import pytest
import subprocess

from pocs.utils.images import fits as fits_utils


@pytest.fixture
def solved_fits_file(data_dir):
    return '{}/solved.fits'.format(data_dir)


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


def test_solve_field(solved_fits_file):
    proc = fits_utils.solve_field(solved_fits_file, verbose=True)
    assert isinstance(proc, subprocess.Popen)
    proc.wait()
    assert proc.returncode == 0


def test_solve_options(solved_fits_file):
    proc = fits_utils.solve_field(
        solved_fits_file, solve_opts=['--guess-scale'], verbose=False)
    assert isinstance(proc, subprocess.Popen)
    proc.wait()
    assert proc.returncode == 0


def test_solve_bad_field(solved_fits_file):
    proc = fits_utils.solve_field('Foo', verbose=True)
    outs, errs = proc.communicate()
    assert 'ERROR' in outs
