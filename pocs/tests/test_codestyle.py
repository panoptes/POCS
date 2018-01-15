import pycodestyle
import pytest


def test_conformance():
    """Test that we conform to PEP-8."""
    style = pycodestyle.StyleGuide(quiet=False, ignore=['E501', 'E402'])
    dirs_to_check = ['pocs', 'peas']

    for d in dirs_to_check:
        style.input_dir(d)
        result = style.check_files()
        assert result.total_errors == 0, "Found code style errors (and warnings)."
