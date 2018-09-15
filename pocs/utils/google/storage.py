import os
import re
import time
import subprocess
import shutil
from warnings import warn
from glob import glob

# Supporting a change in Google Cloud libraries by trying imports both ways:
try:  # pragma: no cover
    # New way:
    from google.cloud import storage
    from google.cloud import exceptions
except ImportError:  # pragma: no cover
    # Old way:
    from gcloud import storage
    from gcloud import exceptions

from pocs.utils.logger import get_root_logger
from pocs.utils.config import load_config
from pocs.utils import error


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
            "Cannot use google storage without a valid auth_key.")

        super(PanStorage, self).__init__()

        self.unit_id = load_config()['pan_id']
        assert re.match(r'PAN\d\d\d', self.unit_id) is not None

        self.project_id = project_id
        self.bucket_name = bucket_name

        self.client = storage.Client.from_service_account_json(
            auth_key,
            project=self.project_id
        )

        try:
            self.bucket = self.client.get_bucket(bucket_name)
        except exceptions.Forbidden:
            raise error.GoogleCloudError(
                "Storage bucket does not exist or no permissions. " +
                "Ensure that the auth_key has valid permissions to the bucket."
            )

        self.logger.info("Connected to storage bucket {}", self.bucket_name)

    def upload_file(self, local_path, remote_path=None):
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

        # Prepend the unit id
        if not remote_path.startswith(self.unit_id):
            remote_path = os.path.join(self.unit_id, remote_path)

        self.logger.debug('Uploading file: {} to bucket: {} object: {} ',
                          local_path, self.bucket.name, remote_path)

        try:
            self.bucket.blob(remote_path).upload_from_filename(
                filename=local_path)
            self.logger.debug('Upload complete')

        except Exception as err:
            self.logger.warning(
                'Problem uploading file {}: {}'.format(local_path, err))

        return remote_path

    def get_file(self, blob_name):
        """Returns an individual blob.

        Args:
            blob_name (str): Full name of Blob to be fetched.

        Returns:
            google.cloud.storage.blob.Blob|None: Blob object or None.
        """
        return self.bucket.get_blob(blob_name)

    def get_files(self, prefix, filter_ext=None, include_pointing=False):
        """Returns the list of Storage blobs (files) matching the prefix.

        Note:
            The prefix can be any pattern, e.g:
                - 'PAN006'  # All images for unit
                - 'Hd189733'  # All images for field
                - 'PAN006/Hd189733/7bab97' # All images for unit, field, camera
                - 'PAN006/*/7bab97' # All images for unit, camera
                - 'PAN006/Hd189733/7bab97/20180327T071126/' # Specific observation

        Args:
            prefix (str): Path in storage to observation sequence, see note.
            filter_ext (str, optional): Filter by filename extension, e.g. '.fz'.
            include_pointing (bool, optional): Whether or not to include the pointing file,
                default False.

        Returns:
            google.cloud.storage.blob.Blob: Blob object.
        """
        objs = list()
        for blob in self.bucket.list_blobs(prefix=prefix):
            if 'pointing' in blob.name and not include_pointing:
                continue
            elif filter_ext is not None and blob.name.endswith(filter_ext) is False:
                continue
            else:
                objs.append(blob)

        return sorted(objs, key=lambda x: x.name)

    def download_file(self, remote_path, save_dir='.', force=False, callback=None):
        """Downloads (and uncompresses) the image blob data.

        Args:
            remote_path (str|`google.cloud.storage.blob.Blob`): Blob or path to remote blob.
                If just the blob name is given then file will be downloaded.
            save_dir (str, optional): Path for saved file, defaults to current directory.
            force (bool, optional): Force a download even if file exists locally, default False.
            callback (callable, optional): A callable object that gets called at end of
                function.

        Returns:
            str: Path to local (uncompressed) FITS file
        """
        # Get blob object if just a path
        if isinstance(remote_path, str):
            remote_path = self.get_file(remote_path)

        output_path = os.path.join(
            save_dir,
            remote_path.name.replace('/', '_')
        )

        # Make dir if needed
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # If we don't  have file (or force=True) then download directly to
        # (compressed) FITS file.
        if not os.path.exists(output_path) or force:
            with open(output_path, 'wb') as f:
                remote_path.download_to_file(f)

        # Wait for download
        timeout = 10
        while os.path.exists(output_path) is False:
            timeout -= 1
            if timeout < 0:
                return None
            time.sleep(1)

        # User supplied callback
        if callback is not None:
            try:
                callback()
            except TypeError:
                warn('callback must be callable')

        return output_path

    def lookup_fits_header(self, remote_blob, parse_line=None):
        """Read the FITS header from storage.

        FITS Header Units are stored in blocks of 2880 bytes consisting of 36 lines
        that are 80 bytes long each. The Header Unit always ends with the single
        word 'END' on a line (not necessarily line 36).

        Here the header is streamed from Storage until the 'END' is found, with
        each line given minimal parsing.

        See https://fits.gsfc.nasa.gov/fits_primer.html for overview of FITS format.

        Args:
            remote_blob (google.cloud.storage.blob.Blob): Blob object
                corresponding to stored FITS file.
            parse_line (callable, optional): A callable function which will be
                passed an 80 character string corresponding to each line in the header.

        Returns:
            dict: FITS header as a dictonary.
        """
        i = 1
        if remote_blob.name.endswith('.fz'):
            i = 2  # We skip the compression header info

        headers = dict()

        streaming = True
        while streaming:
            # Get a header card
            start_byte = 2880 * (i - 1)
            end_byte = (2880 * i) - 1
            b_string = remote_blob.download_as_string(start=start_byte, end=end_byte)

            # Loop over 80-char lines
            for j in range(0, len(b_string), 80):
                item_string = b_string[j:j + 80].decode()

                # End of FITS Header, stop streaming
                if item_string.startswith('END'):
                    streaming = False
                    break

                # If custom parse function supplied, call that
                if parse_line is not None:
                    try:
                        parse_line(item_string)
                    except TypeError:
                        warn('parse_line must be callable')
                    continue

                # Get key=value pairs (skip COMMENTS and HISTORY)
                if item_string.find('=') > 0:
                    k, v = item_string.split('=')

                    # Remove FITS comment
                    if ' / ' in v:
                        v = v.split(' / ')[0]

                    v = v.strip()

                    # Cleanup and discover type in dumb fashion
                    if v.startswith("'") and v.endswith("'"):
                        v = v.replace("'", "").strip()
                    elif v.find('.') > 0:
                        v = float(v)
                    elif v == 'T':
                        v = True
                    elif v == 'F':
                        v = False
                    else:
                        v = int(v)

                    headers[k.strip()] = v

            i += 1

        return headers


def upload_observation_to_bucket(pan_id,
                                 dir_name,
                                 include_files='*.fz',
                                 bucket='panoptes-survey',
                                 **kwargs):
    """Upload an observation directory to google cloud storage.

    This is a convenience function for bulk uploading an observation folder to a
    bucket. This assumes that observations are placed within `/images/fields`
    and follow the normal naming convention for observations.

    Note:
        This requires that the command line utility `gsutil` be installed
        and that authentication has properly been set up.

    Args:
        pan_id (str): A string representing the unit id, e.g. PAN001.
        dir_name (str): Full path to directory.
        include_files (str, optional): Filename filter, defaults to
            compressed FITS files '.fz'.
        bucket (str, optional): The bucket to place the files in, defaults
            to 'panoptes-survey'.
        **kwargs: Optional keywords: verbose

    Returns:
        str: A string path used to search for files.
    """
    assert os.path.exists(dir_name)
    assert re.match(r'PAN\d\d\d', pan_id) is not None

    verbose = kwargs.get('verbose', False)

    def _print(msg):
        if verbose:
            print(msg)

    _print("Uploading {}".format(dir_name))

    gsutil = shutil.which('gsutil')
    assert gsutil is not None

    file_search_path = os.path.join(dir_name, include_files)
    if glob(file_search_path):
        # Get just the observation path
        field_dir = dir_name.split('/fields/')[-1]
        remote_path = os.path.normpath(os.path.join(
            bucket,
            pan_id,
            field_dir
        ))

        # normpath strips the trailing slash so add here so files go in directory
        destination = 'gs://{}/'.format(remote_path)
        run_cmd = [gsutil, '-mq', 'cp', '-r', file_search_path, destination]
        _print("Running: {}".format(run_cmd))

        try:
            completed_process = subprocess.run(
                run_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            if completed_process.returncode != 0:
                warn("Problem uploading")
                warn(completed_process.stdout)
            else:
                return True
        except Exception as e:
            warn("Problem uploading: {}".format(e))

    return file_search_path
