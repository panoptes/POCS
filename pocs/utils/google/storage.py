import os
import re
import time
import subprocess
import shutil
from warnings import warn
from glob import glob

from google.cloud import exceptions
from google.cloud import storage

from pocs.utils. config import load_config
from pocs.utils import error
from pocs.utils.images import fits as fits_utils


def get_storage_client_from_key(auth_key=None, project_id='panoptes-survey'):
    """Get the google storage client using an auth_key.

    Args:
        auth_key (str, optional): Pathname to auth_key. Default None, in which case
            the `panoptes_network.auth_key` config item is used.
        project_id (str, optional): Connect to project, default 'panoptes-survey'.

    Returns:
        `google.cloud.storage.Client`: The storage client.
    """
    if auth_key is None:
        config = load_config()

        try:
            auth_key = config['panoptes_network']['auth_key']
        except KeyError as e:
            raise error.GoogleCloudError(
                "Can't connect to project {}. ".format(project_id) +
                "Ensure that `panoptes_network.auth_key` is set in the config."
            )

    client = storage.Client.from_service_account_json(
        auth_key,
        project=project_id
    )

    return client


def get_bucket(name, client=None, **kwargs):
    """Get Storage bucket object.

    Args:
        name (str): Name of Storage bucket.
        **kwargs: Arguments passed to `get_storage_client`.

    Returns:
        google.cloud.storage.client.Client|None: Stroage Client or None
            if bucket does not exist.

    Raises:
        GoogleCloudError: Description
    """

    if client is None:
        client = get_storage_client_from_key(**kwargs)
    
    bucket = None

    try:
        bucket = client.get_bucket(name)
    except exceptions.Forbidden as e:
        raise error.GoogleCloudError(
            "Storage bucket does not exist or no permissions. " +
            "Ensure that `panoptes_network.auth_key` is set in the config."
        )

    return bucket


def get_observation_blob(blob_name, bucket_name='panoptes-survey', **kwargs):
    """Returns an individual Blob.

    Args:
        blob_name (str): Full name of Blob to be fetched.
        bucket_name (str, optional): Name of Storage bucket where Observation is
            stored, default `panoptes-survey` (Shouldn't need to change).

    Returns:
        google.cloud.storage.blob.Blob|None: Blob object or None.
    """
    return get_bucket(bucket_name, **kwargs).get_blob(blob_name)


def get_observation_blobs(prefix, include_pointing=False, bucket_name='panoptes-survey', **kwargs):
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
        include_pointing (bool, optional): Whether or not to include the pointing file,
            default False.
        bucket_name (str, optional): Name of Storage bucket where Observation is
            stored, default `panoptes-survey` (Shouldn't need to change).

    Returns:
        google.cloud.storage.blob.Blob: Blob object.
    """

    # The bucket we will use to fetch our objects
    bucket = get_bucket(bucket_name, **kwargs)

    objs = list()
    for f in bucket.list_blobs(prefix=prefix):
        if 'pointing' in f.name and not include_pointing:
            continue
        elif f.name.endswith('.fz') is False:
            continue
        else:
            objs.append(f)

    return sorted(objs, key=lambda x: x.name)


def download_fits_file(img_blob, save_dir='.', force=False, unpack=False, callback=None, **kwargs):
    """Downloads (and uncompresses) the image blob data.

    Args:
        img_blob (str|google.cloud.storage.blob.Blob): Blob object corresponding to FITS file.
            If just the blob name is given then file will be downloaded.
        save_dir (str, optional): Path for saved file, defaults to current directory.
        force (bool, optional): Force a download even if file exists locally, default False.
        unpack (bool, optional): If file should be uncompressed, default False.
        callback (callable, optional): A callable object that gets called at end of
        function.

    Returns:
        str: Path to local (uncompressed) FITS file
    """
    if isinstance(img_blob, str):
        img_blob = get_observation_blob(img_blob, **kwargs)

    output_path = os.path.join(
        save_dir,
        img_blob.name.replace('/', '_')
    )

    # Make dir if needed
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # If we don't  have file (or force=True) then download directly to
    # (compressed) FITS file.
    if not os.path.exists(output_path):
        with open(output_path, 'wb') as f:
            img_blob.download_to_file(f)

    # Wait for download
    timeout = 10
    while os.path.exists(output_path) is False:
        timeout -= 1
        if timeout < 0:
            return None
        time.sleep(1)

    # Once downloaded, uncompress
    if os.path.exists(output_path) and unpack:
        output_path = fits_utils.fpack(output_path, unpack=True)

    # User supplied callback (e.g. logging)
    if callback is not None:
        try:
            callback()
        except TypeError as e:
            warn('callback must be callable')

    return output_path


def upload_fits_file(img_path, bucket_name='panoptes-survey', **kwargs):
    """Uploads an image to the storage bucket.

    Args:
        img_path (str): Path to local file to upload.
        bucket_name (str, optional): Bucket to upload, default 'panoptes-survey'.

    """
    bucket = get_bucket(bucket_name, **kwargs)

    # Replace anything before the unit id
    assert re.match('PAN\d\d\d', img_path) is not None
    bucket_path = re.sub(r'^.*PAN', 'PAN', img_path).replace('_', '/')

    try:
        blob = bucket.blob(bucket_path)
        blob.upload_from_filename(img_path)
    except Exception as e:
        warn("Can't upload file: {}".format(e))


def get_header(img_blob, parse_line=None):
    """Read the FITS header from storage.

    FITS Header Units are stored in blocks of 2880 bytes consisting of 36 lines
    that are 80 bytes long each. The Header Unit always ends with the single
    word 'END' on a line (not necessarily line 36).

    Here the header is streamed from Storage until the 'END' is found, with
    each line given minimal parsing.

    See https://fits.gsfc.nasa.gov/fits_primer.html for overview of FITS format.

    Args:
        img_blob (google.cloud.storage.blob.Blob): Blob object corresponding to stored FITS file.
        parse_line (callable, optional): A callable function which will be passed an 80 character
            string corresponding to each line in the header.

    Returns:
        dict: FITS header as a dictonary.
    """
    i = 1
    if img_blob.name.endswith('.fz'):
        i = 2  # We skip the compression header info

    headers = dict()

    streaming = True
    while streaming:
        # Get a header card
        start_byte = 2880 * (i - 1)
        end_byte = (2880 * i) - 1
        b_string = img_blob.download_as_string(start=start_byte, end=end_byte)

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
                except TypeError as e:
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


def upload_directory_to_bucket(pan_id, dir_name, bucket='panoptes-survey', **kwargs):
    """Upload an observation directory to google cloud storage.

    Note:
        This requires that the command line utility `gsutil` be installed
        and that authentication has properly been set up.

    Args:
        pan_id (str): A string representing the unit id, e.g. PAN001.
        dir_name (str): Full path to observation directory.
        bucket (str, optional): The bucket to place the images in, defaults
            to 'panoptes-survey'.
        **kwargs: Optional keywords: verbose
    """
    assert os.path.exists(dir_name)
    assert re.match('PAN\d\d\d', pan_id) is not None

    verbose = kwargs.get('verbose', False)

    def _print(msg):
        if verbose:
            print(msg)

    dir_name = dir_name.replace('//', '/')
    _print("Uploading {}".format(dir_name))

    gsutil = shutil.which('gsutil')

    img_path = os.path.join(dir_name, '*.fz')
    if glob(img_path):
        field_dir = dir_name.split('/fields/')[-1]
        remote_path = os.path.normpath(os.path.join(pan_id, field_dir))

        bucket = 'gs://{}/'.format(bucket)
        # normpath strips the trailing slash so add here so we place in directory
        run_cmd = [gsutil, '-mq', 'cp', '-r', img_path, bucket + remote_path + '/']
        _print("Running: {}".format(run_cmd))

        try:
            completed_process = subprocess.run(run_cmd, stdout=subprocess.PIPE)

            if completed_process.returncode != 0:
                warn("Problem uploading")
                warn(completed_process.stdout)
        except Exception as e:
            warn("Problem uploading: {}".format(e))


def upload_to_bucket(bucket, local_path, remote_path):
    """ Upload to Google Storage Bucket using gsutil.

    Note:
        This function does no sanity checking on `remote_path`.

    See also: `upload_directory` and `upload_fits_file()` for more
    convenient functions.

    Args:
        bucket (str): Bucket name.
        local_path (str): Path to local file.
        remote_path (str): Path to remote file.
    """
    gsutil = shutil.which('gsutil')
    assert gsutil is not None, "gsutil command line utility not found"

    bucket = 'gs://{}/'.format(bucket)
    # normpath strips the trailing slash so add here so we place in directory
    run_cmd = [gsutil, '-mq', 'cp', local_path, bucket + remote_path]
    print("Running: {}".format(run_cmd))

    try:
        completed_process = subprocess.run(run_cmd, stdout=subprocess.PIPE)

        if completed_process.returncode != 0:
            print("Problem uploading")
            print(completed_process.stdout)
    except Exception as e:
        print("Problem uploading: {}".format(e))
