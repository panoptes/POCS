import pytest
import requests

from panoptes.utils import error
from panoptes.utils.config.client import set_config
from panoptes.pocs.scheduler import create_scheduler_from_config
from panoptes.pocs.scheduler import BaseScheduler
from panoptes.pocs.utils.location import create_location_from_config
from panoptes.utils.serializers import to_json

config_host = 'localhost'
config_port = 6563
url = f'http://{config_host}:{config_port}/reset-config'


def reset_conf():
    response = requests.post(url,
                             data=to_json({'reset': True}),
                             headers={'Content-Type': 'application/json'}
                             )
    assert response.ok


def test_bad_scheduler_type():
    set_config('scheduler.type', 'foobar')
    site_details = create_location_from_config()
    with pytest.raises(error.NotFound):
        create_scheduler_from_config(observer=site_details['observer'])

    reset_conf()


def test_bad_scheduler_fields_file():
    set_config('scheduler.fields_file', 'foobar')
    site_details = create_location_from_config()
    with pytest.raises(error.NotFound):
        create_scheduler_from_config(observer=site_details['observer'])

    reset_conf()


def test_no_observer():
    assert isinstance(create_scheduler_from_config(observer=None), BaseScheduler) is True


def test_no_scheduler_in_config():
    set_config('scheduler', None)
    site_details = create_location_from_config()
    assert create_scheduler_from_config(
        observer=site_details['observer']) is None
    reset_conf()
