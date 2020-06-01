import pytest

from panoptes.utils import error
from panoptes.utils.config.client import set_config
from panoptes.pocs.scheduler import create_scheduler_from_config
from panoptes.pocs.scheduler import BaseScheduler
from panoptes.pocs.utils.location import create_location_from_config


def test_bad_scheduler_type(dynamic_config_server, config_port):
    set_config('scheduler.type', 'foobar', port=config_port)
    site_details = create_location_from_config(config_port=config_port)
    with pytest.raises(error.NotFound):
        create_scheduler_from_config(observer=site_details['observer'], config_port=config_port)


def test_bad_scheduler_fields_file(dynamic_config_server, config_port):
    set_config('scheduler.fields_file', 'foobar', port=config_port)
    site_details = create_location_from_config(config_port=config_port)
    with pytest.raises(error.NotFound):
        create_scheduler_from_config(observer=site_details['observer'], config_port=config_port)


def test_no_observer():
    assert isinstance(create_scheduler_from_config(observer=None), BaseScheduler) is True


def test_no_scheduler_in_config(dynamic_config_server, config_port):
    set_config('scheduler', None, port=config_port)
    site_details = create_location_from_config(config_port=config_port)
    assert create_scheduler_from_config(
        observer=site_details['observer'], config_port=config_port) is None
