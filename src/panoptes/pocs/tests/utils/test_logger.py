import time
import pytest

from panoptes.pocs.utils.logger import get_logger


@pytest.fixture()
def profile():
    return 'testing'


def test_base_logger(caplog, profile, tmp_path):
    logger = get_logger(log_dir=str(tmp_path),
                        full_log_file=None)
    logger.debug('Hello')
    time.sleep(1)  # Wait for log to make it there.
    assert caplog.records[-1].message == 'Hello'
    assert caplog.records[-1].levelname == 'DEBUG'
