import time
import os
import pytest

from pocs.utils.logger import get_logger


@pytest.fixture()
def profile():
    return 'testing'


def test_logger_output(caplog, profile, tmp_path):
    console_log_file = os.path.join(str(tmp_path), 'testing.log')
    logger = get_logger(console_log_file='testing.log',
                        log_dir=str(tmp_path),
                        profile=profile)
    msg = "You will see me"
    logger.debug(msg)
    time.sleep(0.01)  # Give it time to write.

    assert len(caplog.records) == 1

    # But is in file
    assert os.path.exists(console_log_file)
    with open(console_log_file, 'r') as f:
        assert msg in f.read()


def test_base_logger(caplog, profile, tmp_path):
    logger = get_logger(log_dir=str(tmp_path), profile=profile)
    logger.debug('Hello')
    assert caplog.records[-1].message == 'Hello'
