import pytest
import os

from pocs.utils.error import GoogleCloudError
from pocs.utils.google.storage import PanStorage


pytestmark = pytest.mark.skipif(
    not pytest.config.option.test_cloud_storage,
    reason="Needs --test-cloud-storage to run"
)


def test_key_exists():
    assert os.environ['PANOPTES_CLOUD_KEY']
    assert os.path.exists(os.environ['PANOPTES_CLOUD_KEY'])


def test_bad_bucket():
    with pytest.raises(AssertionError):
        PanStorage('fake-bucket')

    auth_key_path = os.environ['PANOPTES_CLOUD_KEY']
    with pytest.raises(GoogleCloudError):
        PanStorage('fake-bucket', auth_key=auth_key_path)


@pytest.fixture(scope="function")
def storage():
    auth_key_path = os.environ['PANOPTES_CLOUD_KEY']
    return PanStorage('panoptes-test-bucket', auth_key=auth_key_path)


def test_unit_id(storage):
    assert storage.unit_id is not None
    # TODO(wtgee)Verify the unit id better after #384 is done.
    assert storage.unit_id.startswith('PAN'), storage.logger.error(
        "Must have valid PAN_ID. Please change your conf_files/pocs_local.yaml")


def test_bucket_exists(storage):
    assert storage.bucket.exists()


def test_file_upload_no_prepend(storage):
    temp_fn = 'ping.txt'
    with open(temp_fn, 'w') as f:
        f.write('Hello World')

    remote_path = storage.upload(temp_fn)
    assert remote_path == '{}/{}'.format(storage.unit_id, temp_fn)
    assert storage.bucket.blob(remote_path).exists()
    os.unlink(temp_fn)


def test_file_upload_prepend_remote_path(storage):
    temp_fn = 'pong.txt'.format(storage.unit_id)
    with open(temp_fn, 'w') as f:
        f.write('Hello World')

    remote_path = '{}/{}'.format(storage.unit_id, temp_fn)
    returned_remote_path = storage.upload(temp_fn, remote_path=remote_path, quiet=True)
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
    assert storage.bucket.blob(remote_path).exists() is False
