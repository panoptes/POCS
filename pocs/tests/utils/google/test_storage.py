import pytest
import os
import shutil

from panoptes.utils.error import GoogleCloudError
from panoptes.utils.google import is_authenticated
from panoptes.utils.google.storage import PanStorage, upload_observation_to_bucket


pytestmark = pytest.mark.skipif(
    not pytest.config.option.test_cloud_storage,
    reason="Needs --test-cloud-storage to run."
)

pytestmark = pytest.mark.skipif(
    not is_authenticated(),
    reason="Not authenticated on Google network."
)


def test_bad_bucket():
    with pytest.raises(AssertionError):
        PanStorage('fake-bucket')

    with pytest.raises(GoogleCloudError):
        PanStorage('fake-bucket')


@pytest.fixture(scope="function")
def storage():
    return PanStorage('panoptes-test-bucket')


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
