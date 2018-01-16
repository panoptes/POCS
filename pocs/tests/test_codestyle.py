import pycodestyle
import pytest


@pytest.fixture(scope='module', params=['pocs', 'peas'])
def dirs_to_check(request):
    return request.param


def test_conformance(dirs_to_check):
    """Test that we conform to PEP-8."""
    style = pycodestyle.StyleGuide(quiet=False, ignore=['E501', 'E402'])

    print(dirs_to_check)
    style.input_dir(dirs_to_check)
    result = style.check_files()
    assert result.total_errors == 0, "Found code style errors (and warnings)."
