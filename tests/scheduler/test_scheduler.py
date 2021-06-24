import pytest
import requests

from panoptes.utils import error
from panoptes.utils.config.client import set_config
from panoptes.pocs.scheduler import create_scheduler_from_config
from panoptes.pocs.scheduler import BaseScheduler
from panoptes.pocs.utils.location import create_location_from_config
from panoptes.utils.serializers import to_json


def reset_conf(config_host, config_port):
    url = f'http://{config_host}:{config_port}/reset-config'
    response = requests.post(url,
                             data=to_json({'reset': True}),
                             headers={'Content-Type': 'application/json'}
                             )
    assert response.ok


def test_bad_scheduler_namespace(config_host, config_port):
    set_config('scheduler.type', 'dispatch')
    site_details = create_location_from_config()
    with pytest.raises(error.NotFound):
        create_scheduler_from_config(observer=site_details['observer'])

    set_config('scheduler.type', 'panoptes.pocs.scheduler.dispatch')
    scheduler = create_scheduler_from_config(observer=site_details['observer'])

    assert isinstance(scheduler, BaseScheduler)

    reset_conf(config_host, config_port)


def test_bad_scheduler_type(config_host, config_port):
    set_config('scheduler.type', 'foobar')
    site_details = create_location_from_config()
    with pytest.raises(error.NotFound):
        create_scheduler_from_config(observer=site_details['observer'])

    reset_conf(config_host, config_port)


def test_bad_scheduler_fields_file(config_host, config_port):
    set_config('scheduler.fields_file', 'foobar')
    site_details = create_location_from_config()
    with pytest.raises(error.NotFound):
        create_scheduler_from_config(observer=site_details['observer'])

    reset_conf(config_host, config_port)


def test_no_observer():
    assert isinstance(create_scheduler_from_config(observer=None), BaseScheduler) is True


def test_no_scheduler_in_config(config_host, config_port):
    set_config('scheduler', None)
    site_details = create_location_from_config()
    assert create_scheduler_from_config(
        observer=site_details['observer']) is None
    reset_conf(config_host, config_port)
