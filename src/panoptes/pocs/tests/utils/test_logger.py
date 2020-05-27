import time
import pytest

from panoptes.pocs.utils.logger import get_logger


@pytest.fixture()
def profile():
    return 'testing'


def test_base_logger(caplog, profile, tmp_path):
    logger = get_logger(log_dir=str(tmp_path),
                        full_log_file=None,
                        profile=profile)
    logger.debug('Hello')
    time.sleep(0.5)
    assert caplog.records[-1].message == 'Hello'
    assert caplog.records[-1].levelname == 'DEBUG'
