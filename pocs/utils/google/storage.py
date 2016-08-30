import os
import warnings

from gcloud import storage

from pocs import _logger


class PanStorage(object):
    """ Class for interacting with Google Cloud Platform """

    def __init__(self, project_id='panoptes-survey', bucket_name=None, prefix=None):
        assert bucket_name is not None, warnings.warn("A valid bucket name is required.")
        super(PanStorage, self).__init__()

        self.logger = _logger
        self.project_id = project_id
        self.prefix = prefix

        self.client = storage.Client(self.project_id)
        self.bucket_name = bucket_name
        self.bucket = self.client.get_bucket(bucket_name)

    def list_remote(self, prefix=None):
        """Return a list of blobs in the remote bucket with the given prefix."""
        if not prefix:
            prefix = self.prefix

        blobs = self.bucket.list_blobs(prefix=prefix)
        files = []
        for blob in blobs:
            files.append(blob.name)
        return files

    def upload(self, local_path, remote_path=None):
        """Upload the given file to the Google Cloud Storage bucket."""
        assert self.project_id and os.path.exists(local_path)

        self.logger.debug('Building upload request...')

        if remote_path is None:
            remote_path = local_path

        self.logger.debug('Uploading file: %s to bucket: %s object: %s '.format(
            local_path, self.bucket.name, remote_path))

        try:
            self.bucket.blob(remote_path).upload_from_filename(filename=local_path)
            self.logger.debug('Upload complete!')

        except Exception as err:
            self.logger.warning('Problem uploading file {}: {}'.format(local_path, err))

        return remote_path

    def download(self, remote_path, local_path=None):
        """Download the given file from the Google Cloud Storage bucket."""
        if local_path is None:
            local_path = '{}/temp/{}'.format(os.getenv('PANDIR'), remote_path)

        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        try:
            self.bucket.get_blob(remote_path).download_to_filename(filename=local_path)
            self.logger.debug('Download complete!')
        except Exception as err:
            self.logger.warning('Problem downloading {}: {}'.format(remote_path, err))

        return local_path

    def upload_string(self, data, remote_path):
        """Upload the given data string to the Google Cloud Storage bucket."""
        if remote_path in self.list_remote():
            try:
                self.bucket.get_blob(remote_path).upload_from_string(data)
                self.logger.debug('String upload complete!')
            except Exception as err:
                self.logger.warning('Problem uploading string: {}'.format(err))
        else:
            try:
                self.bucket.blob(remote_path).upload_from_string(data)
                self.logger.debug('String upload complete!')
            except Exception as err:
                self.logger.warning('Problem uploading string: {}'.format(err))
        return remote_path

    def download_string(self, remote_path):
        """Download the given file as a string from the Google Cloud Storage bucket."""
        try:
            data = self.bucket.get_blob(remote_path).download_as_string()
            self.logger.debug('String download complete!')
        except Exception as err:
            self.logger.warning('Problem downloading {}: {}'.format(remote_path, err))
        return data


