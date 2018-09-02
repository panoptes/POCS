import pytest
import os
import re
import shutil

from pocs.utils.config import load_config
from pocs.utils.error import GoogleCloudError
from pocs.utils.google.storage import PanStorage, upload_observation_to_bucket


pytestmark = pytest.mark.skipif(
    not pytest.config.option.test_cloud_storage,
    reason="Needs --test-cloud-storage to run"
)


@pytest.fixture(scope="module")
def auth_key():
    local_config = load_config('pocs_local', ignore_local=True)
    auth_key = os.path.join(
        os.environ['PANDIR'],
        '.key',
        local_config['panoptes_network']['auth_key']
    )

    return auth_key


def test_key_exists(auth_key):
    assert os.path.exists(auth_key), "No API key file"


def test_bad_bucket(auth_key):
    with pytest.raises(AssertionError):
        PanStorage('fake-bucket')

    with pytest.raises(GoogleCloudError):
        PanStorage('fake-bucket', auth_key=auth_key)


@pytest.fixture(scope="function")
def storage(auth_key):
    return PanStorage('panoptes-test-bucket', auth_key=auth_key)


def test_unit_id(storage):
    assert storage.unit_id is not None
    # TODO(wtgee)Verify the unit id better after #384 is done.
    assert re.match(r'PAN\d\d\d', storage.unit_id), storage.logger.error(
        "Must have valid pan_id. Please change your conf_files/pocs_local.yaml")


def test_bucket_exists(storage):
    assert storage.bucket.exists()


def test_file_upload_no_prepend(storage):
    temp_fn = 'ping.txt'
    with open(temp_fn, 'w') as f:
        f.write('Hello World')

    remote_path = storage.upload_file(temp_fn)
    assert remote_path == os.path.join(storage.unit_id, temp_fn)
    assert storage.bucket.blob(remote_path).exists()
    os.unlink(temp_fn)


def test_file_upload_prepend_remote_path(storage):
    temp_fn = 'pong.txt'.format(storage.unit_id)
    with open(temp_fn, 'w') as f:
        f.write('Hello World')

    remote_path = os.path.join(storage.unit_id, temp_fn)
    returned_remote_path = storage.upload_file(temp_fn, remote_path=remote_path)
    assert remote_path == returned_remote_path
    assert storage.bucket.blob(returned_remote_path).exists()
    os.unlink(temp_fn)


def test_delete(storage):
    """
    Note: The util wrappers don't provide a way to delete because we generally
    will not want people to delete things. However it's good to test and we
    want to remove the above files
    """
    remote_path = '{}/pong.txt'.format(storage.unit_id)
    assert storage.bucket.blob(remote_path).exists()
    storage.bucket.blob(remote_path).delete()


def test_upload_observation_to_bucket(storage):
    dir_name = os.path.join(
        os.environ['POCS'],
        'pocs', 'tests', 'data'
    )

    # We copy all the files to a temp dir and then upload that to get
    # correct pathnames.
    new_dir = os.path.join('/tmp', 'fields', 'fake_obs')
    shutil.copytree(dir_name, new_dir)

    include_files = '*'

    pan_id = storage.unit_id
    assert upload_observation_to_bucket(
        pan_id,
        new_dir,
        include_files=include_files,
        bucket='panoptes-test-bucket')

    shutil.rmtree(new_dir, ignore_errors=True)
