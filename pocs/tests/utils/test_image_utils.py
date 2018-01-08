import numpy as np
import tempfile
import shutil

from glob import glob

from pocs.utils import images as img_utils


def test_crop_data():
    ones = np.ones((201, 201))
    assert ones.sum() == 40401.

    cropped01 = img_utils.crop_data(ones, verbose=True)
    assert cropped01.sum() == 40000.

    cropped02 = img_utils.crop_data(ones, verbose=True, box_width=10)
    assert cropped02.sum() == 100.

    cropped03 = img_utils.crop_data(ones, verbose=True, box_width=6, center=(50, 50))
    assert cropped03.sum() == 36.


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
