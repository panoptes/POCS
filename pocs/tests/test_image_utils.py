import numpy as np

from pocs.utils import images as img_utils


def test_crop_data():
    ones = np.ones((201, 201))
    assert ones.sum() == 40401.

    cropped01 = img_utils.crop_data(ones, verbose=True)
    assert cropped01.sum() == 40000.

    cropped02 = img_utils.crop_data(ones, verbose=True, box_width=10)
    assert cropped02.sum() == 100.
