import time
import os
import pytest

from pocs.utils.logger import get_logger


@pytest.fixture()
def profile():
    return 'testing'


def test_logger_no_output(caplog, profile, tmp_path):
    console_log_file = os.path.join(str(tmp_path), 'testing.log')
    logger = get_logger(console_log_file='testing.log',
                        log_dir=str(tmp_path),
                        profile=profile)
    msg = "You won't see me"
    logger.debug(msg)
    time.sleep(0.5)  # Give it time to write.

    # Not in stderr output
    assert len(caplog.records) == 0

    # But is in file
    assert os.path.exists(console_log_file)
    with open(console_log_file, 'r') as f:
        assert msg in f.read()


def test_base_logger(caplog, profile, tmp_path):
    logger = get_logger(log_dir=str(tmp_path), profile=profile)
    logger.debug('Hello')
    assert caplog.records[-1].message == 'Hello'


def test_root_logger(caplog, profile, tmp_path):
    logger = get_logger(log_dir=str(tmp_path), profile=profile)
    logger.debug('Hi')
    assert os.listdir(tmp_path)[0].startswith('panoptes_')
    assert caplog.records[-1].message == 'Hi'
    assert caplog.records[-1].levelname == 'DEBUG'

    os.environ['PANLOG'] = str(tmp_path)
    logger = get_logger(console_log_file='foo.log', profile=profile)
    logger.info('Bye', extra=dict(foo='bar'))
    assert len(os.listdir(tmp_path)) == 2
    assert os.listdir(tmp_path)[-1] == 'foo.log'
    assert caplog.records[-1].message == 'Bye'
    assert caplog.records[-1].levelname == 'INFO'

    del os.environ['PANLOG']
    os.environ['PANDIR'] = str(tmp_path)
    logger = get_logger(profile=profile)
    logger.critical('Bye Again')
    dir_name = os.path.join(str(tmp_path), 'logs')
    assert os.path.isdir(dir_name)
    assert len(os.listdir(dir_name)) == 1
    assert caplog.records[-1].message == 'Bye Again'
    assert caplog.records[-1].levelname == 'CRITICAL'
