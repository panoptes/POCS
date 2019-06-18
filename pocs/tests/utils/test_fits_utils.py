import os
import pytest
import subprocess
import shutil

from astropy.io.fits import Header

from panoptes.utils.images import fits as fits_utils


@pytest.fixture
def solved_fits_file(data_dir):
    return os.path.join(data_dir, 'solved.fits.fz')


def test_wcsinfo(solved_fits_file):
    wcsinfo = fits_utils.get_wcsinfo(solved_fits_file)

    assert 'wcs_file' in wcsinfo
    assert wcsinfo['ra_center'].value == 303.206422334


def test_fpack(solved_fits_file):
    new_file = solved_fits_file.replace('solved', 'solved_copy')
    copy_file = shutil.copyfile(solved_fits_file, new_file)
    info = os.stat(copy_file)
    assert info.st_size > 0.

    uncompressed = fits_utils.funpack(copy_file, verbose=True)
    assert os.stat(uncompressed).st_size > info.st_size

    compressed = fits_utils.fpack(uncompressed, verbose=True)
    assert os.stat(compressed).st_size == info.st_size

    os.remove(copy_file)


def test_getheader(solved_fits_file):
    header = fits_utils.getheader(solved_fits_file)
    assert isinstance(header, Header)
    assert header['IMAGEID'] == 'PAN001_XXXXXX_20160909T081152'


def test_getval(solved_fits_file):
    img_id = fits_utils.getval(solved_fits_file, 'IMAGEID')
    assert img_id == 'PAN001_XXXXXX_20160909T081152'


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
    assert 'ERROR' in errs
