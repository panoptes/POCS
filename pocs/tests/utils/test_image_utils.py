import os
import numpy as np
import pytest
import shutil
import tempfile
from glob import glob

from pocs.utils import images as img_utils
from pocs.utils import error


def test_make_images_dir(save_environ):
    assert img_utils.make_images_dir()

    # Invalid parent directory for 'images'.
    os.environ['PANDIR'] = '/dev/null/'
    with pytest.warns(UserWarning):
        assert img_utils.make_images_dir() is None

    # Valid parents for 'images' that need to be created.
    with tempfile.TemporaryDirectory() as tmpdir:
        parent = os.path.join(tmpdir, 'some', 'dirs')
        imgdir = os.path.join(parent, 'images')
        os.environ['PANDIR'] = parent
        assert img_utils.make_images_dir() == imgdir


def test_crop_data():
    ones = np.ones((201, 201))
    assert ones.sum() == 40401.

    cropped01 = img_utils.crop_data(ones, verbose=True)
    assert cropped01.sum() == 40000.

    cropped02 = img_utils.crop_data(ones, verbose=True, box_width=10)
    assert cropped02.sum() == 100.

    cropped03 = img_utils.crop_data(ones, verbose=True, box_width=6, center=(50, 50))
    assert cropped03.sum() == 36.


def test_make_pretty_image(solved_fits_file, tiny_fits_file, save_environ):
    # Not a valid file type (can't automatically handle .fits.fz files).
    with pytest.warns(UserWarning, match='File must be'):
        assert not img_utils.make_pretty_image(solved_fits_file)

    # Make a dir and put test image files in it.
    with tempfile.TemporaryDirectory() as tmpdir:
        fz_file = os.path.join(tmpdir, os.path.basename(solved_fits_file))
        fits_file = os.path.join(tmpdir, os.path.basename(tiny_fits_file))
        # TODO Add a small CR2 file to our sample image files.

        # Can't operate on a non-existent files.
        with pytest.warns(UserWarning, match="File doesn't exist"):
            assert not img_utils.make_pretty_image(fits_file)

        # Copy the files.
        shutil.copy(solved_fits_file, tmpdir)
        shutil.copy(tiny_fits_file, tmpdir)

        # Not a valid file type (can't automatically handle fits.fz files).
        with pytest.warns(UserWarning):
            assert not img_utils.make_pretty_image(fz_file)

        # Can handle the fits file, and creating the images dir for linking
        # the latest image.
        imgdir = os.path.join(tmpdir, 'images')
        assert not os.path.isdir(imgdir)
        os.environ['PANDIR'] = tmpdir

        pretty = img_utils.make_pretty_image(fits_file, link_latest=True)
        assert pretty
        assert os.path.isfile(pretty)
        assert os.path.isdir(imgdir)
        latest = os.path.join(imgdir, 'latest.jpg')
        assert os.path.isfile(latest)
        os.remove(latest)
        os.rmdir(imgdir)

        # Try again, but without link_latest.
        pretty = img_utils.make_pretty_image(fits_file, title='some text')
        assert pretty
        assert os.path.isfile(pretty)
        assert not os.path.isdir(imgdir)


def test_make_pretty_image_cr2_fail():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpfile = os.path.join(tmpdir, 'bad.cr2')
        with open(tmpfile, 'w') as f:
            f.write('not an image file')
        with pytest.raises(error.InvalidCommand):
            img_utils.make_pretty_image(tmpfile, title='some text', link_latest=False)
        with pytest.raises(error.InvalidCommand):
            img_utils.make_pretty_image(tmpfile, verbose=True)


def test_clean_observation_dir(data_dir):
    # First make a dir and put some files in it
    with tempfile.TemporaryDirectory() as tmpdir:
        # Copy fits files
        for f in glob('{}/solved.*'.format(data_dir)):
            shutil.copy(f, tmpdir)

        assert len(glob('{}/solved.*'.format(tmpdir))) == 2

        # Make some jpgs
        for f in glob('{}/*.fits'.format(tmpdir)):
            img_utils.make_pretty_image(f)

        # Cleanup
        img_utils.clean_observation_dir(tmpdir, verbose=True)
