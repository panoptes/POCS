import os
import re

from gcloud import storage
from gcloud.exceptions import Forbidden

from pocs.utils import error
from pocs.utils.logger import get_root_logger
from pocs.utils.config import load_config


class PanStorage(object):
    """ Class for interacting with Google Cloud Platform """

    def __init__(self, bucket_name, auth_key=None, project_id='panoptes-survey'):
        """Create an object that can interact easily with storage buckets.

        Args:
            bucket_name (str): Name of bucket to use.
            auth_key (str, optional): Path to valid json authorization token.
            project_id (str, optional): Project id hosting the bucket. Default 'panoptes-survey'

        Raises:
            error.GoogleCloudError: Error raised if valid connection cannot be formed for
                given project, bucket, and authorization.
        """
        self.logger = get_root_logger()
        assert auth_key is not None and os.path.exists(auth_key), self.logger.error(
            "Cannot use google storage without PANOPTES_CLOUD_KEY variable set.")

        super(PanStorage, self).__init__()

        self.unit_id = load_config()['pan_id']
        assert re.match('PAN\d\d\d', self.unit_id) is not None

        self.project_id = project_id
        self.bucket_name = bucket_name

        self.client = storage.Client.from_service_account_json(auth_key, project=self.project_id)

        try:
            self.bucket = self.client.get_bucket(bucket_name)
        except Forbidden as e:
            raise error.GoogleCloudError(
                "Storage bucket does not exist or no permissions. " +
                "Ensure that the PANOPTES_CLOUD_KEY variable is properly set")

        self.logger.info("Connected to storage bucket {}", self.bucket_name)

    def upload(self, local_path, remote_path=None):
        """Upload the given file to the Google Cloud Storage bucket.

        Note:
            The name of the current unit will be prepended to the path
            so that all files will be placed in a "subdirectory" according
            to unit.

        Args:
            local_path (str): Path to local file to be uploaded
            remote_path (str, optional): Destination path in bucket.

        Returns:
            str: Remote path of uploaded object
        """
        assert os.path.exists(local_path), self.logger.warning(
            "Local path does not exist, can't upload: {}", local_path)

        if remote_path is None:
            remote_path = local_path

        if not remote_path.startswith(self.unit_id):
            remote_path = '{}/{}'.format(self.unit_id, remote_path)

        self.logger.debug('Uploading file: {} to bucket: {} object: {} ', local_path,
                          self.bucket.name, remote_path)

        try:
            self.bucket.blob(remote_path).upload_from_filename(filename=local_path)
            self.logger.debug('Upload complete')

        except Exception as err:
            self.logger.warning('Problem uploading file {}: {}'.format(local_path, err))

        return remote_path
