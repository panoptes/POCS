import pytest

from pocs.scheduler import create_scheduler_from_config, BaseScheduler
from pocs.utils import error
from pocs.utils.location import create_location_from_config


def test_bad_scheduler_type(config):
    conf = config.copy()
    conf['scheduler']['type'] = 'foobar'
    site_details = create_location_from_config(config)
    with pytest.raises(error.NotFound):
        create_scheduler_from_config(conf, observer=site_details['observer'])


def test_bad_scheduler_fields_file(config):
    conf = config.copy()
    conf['scheduler']['fields_file'] = 'foobar'
    site_details = create_location_from_config(config)
    with pytest.raises(error.NotFound):
        create_scheduler_from_config(conf, observer=site_details['observer'])


def test_no_observer(config):
    assert isinstance(create_scheduler_from_config(config, observer=None), BaseScheduler) is True


def test_no_scheduler_in_config(config):
    conf = config.copy()
    del conf['scheduler']
    site_details = create_location_from_config(conf)
    assert create_scheduler_from_config(conf, observer=site_details['observer']) is None
