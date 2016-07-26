import pycodestyle
import pytest


def test_conformance():
    """Test that we conform to PEP-8."""
    style = pycodestyle.StyleGuide(quiet=False, ignore=['E501'])
    style.input_dir('pocs')
    result = style.check_files()
    assert result.total_errors == 0, "Found code style errors (and warnings)."
