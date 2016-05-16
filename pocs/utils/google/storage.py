import os
import warnings

from gcloud import storage

from astropy.utils import console
from pocs import _logger


class PanStorage(object):
    """ Class for interacting with Google Cloude Platform """

    def __init__(self, project_id='panoptes-survey', bucket=None, prefix=None):
        assert bucket is not None, warnings.warn("A valid bucket is required.")
        super(PanStorage, self).__init__()

        self.logger = _logger
        self.project_id = project_id
        self.bucket = bucket
        self.prefix = prefix

        self.client = storage.Client(self.project_id)
        self.bucket = self.client.get_bucket(bucket)

    def list_remote(self, prefix=None):

        if not prefix:
            prefix = self.prefix

        blobs = self.storage.list_blobs(prefix=prefix)

        for blob in blobs:
            self.logger.debug(blob)
            console.color_print(blob.name)

        return blobs

    def upload(self, local_path, remote_path=None):
        assert self.project_id and os.path.exists(local_path)

        self.logger.debug('Building upload request...')

        if remote_path is None:
            remote_path = local_path.rstrip('/').split('/')[-1]

        self.logger.debug('Uploading file: %s to bucket: %s object: %s '.format(
            local_path, self.project_id, remote_path))

        try:
            self.bucket.blob(remote_path).upload_from_filename(filename=local_path)
        except Exception as err:
            self.logger.warning("Problem uplading file {}: {}".format(local_path, err))

        self.logger.debug('\nUpload complete!')

        return True

    def download(self, remote_path, local_path=None):

        if local_path is None:
            local_path = '/var/panoptes/temp/{}'.format(remote_path.rstrip('/').split('/')[-1])

            try:
                self.bucket.get_blob(remote_path).download_to_filename(filenmae=local_path)
                self.logger.debug('Download complete!')
            except Exception as err:
                self.logger.warning("Problem downlading {}: {}".format(remote_path, err))
            else:
                return True
