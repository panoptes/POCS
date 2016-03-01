

"""
Command-line application that interacts with Google Cloud Storage

"""

import os
import random
import time
import httplib2
from googleapiclient import discovery
from oauth2client.client import GoogleCredentials

from apiclient.errors import HttpError
from apiclient.http import MediaFileUpload
from apiclient.http import MediaIoBaseDownload
from json import dumps as json_dumps

from astropy.utils import console

from ..logger import get_logger


class PanStorage(object):
    # Retry transport and file IO errors.
    RETRYABLE_ERRORS = (httplib2.HttpLib2Error, IOError)

    # Number of times to retry failed downloads.
    NUM_RETRIES = 5

    # Number of bytes to send/receive in each request.
    CHUNKSIZE = 2 * 1024 * 1024

    # Mimetype to use if one can't be guessed from the file extension.
    DEFAULT_MIMETYPE = 'application/octet-stream'

    """ Class for interacting with Google BigQuery """

    def __init__(self, project_id='panoptes-survey', bucket='panoptes-survey'):
        super(PanStorage, self).__init__()
        self.logger = get_logger(self)
        self.project_id = project_id
        self.bucket = bucket

        # Grab the application's default credentials from the environment.
        self.credentials = GoogleCredentials.get_application_default()

        # Construct the service object for interacting with the BigQuery API.
        self.storage = discovery.build('storage', 'v1', credentials=self.credentials)

    def log(self, msg, color='default'):
        console.color_print(msg, color)

    def list_remote(self, prefix='PAN001/'):

        fields_to_return = 'nextPageToken,items(name,size,contentType)'

        req = self.storage.objects().list(bucket=self.bucket, fields=fields_to_return, prefix=prefix)
        resp = req.execute()

        return resp

    def upload(self, local_path, remote_path=None):
        assert self.project_id and os.path.exists(local_path)

        self.log('Building upload request...')
        media = MediaFileUpload(local_path, chunksize=self.CHUNKSIZE, resumable=True)

        if not media.mimetype():
            media = MediaFileUpload(local_path, self.DEFAULT_MIMETYPE, resumable=True)

        if remote_path is None:
            remote_path = local_path.rsplit('/').split('/')[-1]

        request = self.storage.objects().insert(bucket=self.project_id, name=remote_path, media_body=media)

        self.log('Uploading file: %s to bucket: %s object: %s '.format(local_path, self.project_id, remote_path))

        progressless_iters = 0
        response = None

        with console.ProgressBarOrSpinner(1.0, "Upload status") as bar:
            while response is None:
                error = None
                try:
                    progress, response = request.next_chunk()
                    bar.update(progress.progress())
                except HttpError as err:
                    error = err
                    if err.resp.status < 500:
                        raise
                except self.RETRYABLE_ERRORS as err:
                    error = err

                if error:
                    progressless_iters += 1
                    self.handle_progressless_iter(error, progressless_iters)
                else:
                    progressless_iters = 0

        response_obj = json_dumps(response, indent=2)

        self.log('\nUpload complete!')
        self.log('Uploaded Object:')
        self.log(response_obj)

        return response_obj

    def download(self, remote_path, local_path=None):

        self.log('Building download request...')

        if local_path is None:
            local_path = '/var/panoptes/temp/{}'.format(remote_path.rstrip('/').split('/')[-1])

        with open(local_path, 'wb') as f:
            request = self.storage.objects().get_media(bucket=self.project_id, object=remote_path)
            media = MediaIoBaseDownload(f, request, chunksize=self.CHUNKSIZE)

            self.log('Downloading bucket: {} object: {} to file: {}'.format(self.project_id, remote_path, local_path))

            progressless_iters = 0
            done = False

            with console.ProgressBarOrSpinner(1.0, 'Download status') as bar:
                while not done:
                    error = None
                    try:
                        progress, done = media.next_chunk()
                        bar.update(progress.progress())
                    except HttpError as err:
                        error = err
                        if err.resp.status < 500:
                            raise
                    except self.RETRYABLE_ERRORS as err:
                        error = err

                    if error:
                        progressless_iters += 1
                        self.handle_progressless_iter(error, progressless_iters)
                    else:
                        progressless_iters = 0

            self.log('Download complete!')

    def handle_progressless_iter(self, error, progressless_iters):
        if progressless_iters > self.NUM_RETRIES:
            self.log('Failed to make progress for too many consecutive iterations.')
            raise error

        sleeptime = random.random() * (2**progressless_iters)
        self.log('Caught exception ({}). Sleeping for {} seconds before retry #{}.',
                 format(str(error), sleeptime, progressless_iters))
        time.sleep(sleeptime)
