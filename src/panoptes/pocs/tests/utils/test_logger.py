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

    see_log = False
    for rec in caplog.records[-5:]:
        if rec.message == 'Hello':
            see_log = True

    assert see_log
