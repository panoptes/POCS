#!/usr/bin/env python
import os
import re
from glob import glob
from contextlib import suppress

import subprocess
import shutil

from panoptes.utils import error
from panoptes.pocs.utils.logger import get_logger
from panoptes.utils.config.client import get_config
from panoptes.utils.images import fits as fits_utils
from panoptes.utils.images import make_timelapse

logger = get_logger()


def upload_observation_to_bucket(pan_id,
                                 dir_name,
                                 include_files='*.fz',
                                 bucket='panoptes-exp',
                                 **kwargs):
    """Upload an observation directory to google cloud storage.

    This is a convenience function for bulk uploading an observation folder to a
    bucket. This assumes that observations are placed within `/images/fields`
    and follow the normal naming convention for observations.

    Note:
        This requires that the command line utility `gsutil` be installed
        and that authentication has properly been set up.

    TODO(wtgee): This could be merged into the PanStorage class.

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
    if os.path.exists(dir_name) is False:
        raise OSError("Directory does not exist, cannot upload: {}".format(dir_name))

    if re.match(r'PAN\d\d\d$', pan_id) is None:
        raise Exception("Invalid PANID. Must be of the form 'PANnnn'. Got: {!r}".format(pan_id))

    gsutil = shutil.which('gsutil')
    if gsutil is None:  # pragma: no cover
        raise Exception('Cannot find gsutil, skipping upload')

    logger.debug(f"Uploading {dir_name}")

    file_search_path = os.path.join(dir_name, include_files)
    if glob(file_search_path):
        # Get just the observation path
        field_dir = dir_name.split('/images/')[-1]
        remote_path = os.path.normpath(os.path.join(
            bucket,
            pan_id,
            field_dir
        ))
        destination = f'gs://{remote_path}/'

        script_name = os.path.join(os.environ['POCS'], 'scripts', 'transfer-files.sh')
        manifest_file = os.path.join(dir_name, 'upload_manifest.log')
        run_cmd = [script_name, file_search_path, destination, manifest_file]

        if pan_id == 'PAN000':
            run_cmd = [gsutil, 'PAN000 upload should fail']

        logger.debug("Running: {}".format(run_cmd))

        try:
            completed_process = subprocess.run(
                run_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            if completed_process.returncode != 0:
                raise Exception(completed_process.stderr)
        except Exception as e:
            raise error.GoogleCloudError("Problem with upload: {}".format(e))

    return file_search_path


def clean_observation_dir(dir_name,
                          remove_jpgs=False,
                          include_timelapse=True,
                          timelapse_overwrite=False,
                          **kwargs):
    """Clean an observation directory.
    For the given `dir_name`, will:
        * Compress FITS files
        * Remove `.solved` files
        * Create timelapse from JPG files if present (optional, default True)
        * Remove JPG files (optional, default False).
    Args:
        dir_name (str): Full path to observation directory.
        remove_jpgs (bool, optional): If JPGs should be removed after making timelapse,
            default False.
        include_timelapse (bool, optional): If a timelapse should be created, default True.
        timelapse_overwrite (bool, optional): If timelapse file should be overwritten,
            default False.
        **kwargs: Can include `verbose`.
    """

    def _glob(s):
        return glob(os.path.join(dir_name, s))

    logger.info("Cleaning dir: {}".format(dir_name))

    # Pack the fits files
    logger.debug("Packing FITS files")
    for f in _glob('*.fits'):
        try:
            fits_utils.fpack(f)
        except Exception as e:  # pragma: no cover
            logger.warning('Could not compress fits file: {!r}'.format(e))

    # Remove .solved files
    logger.debug('Removing .solved files')
    for f in _glob('*.solved'):
        with suppress(OSError):
            os.remove(f)

    try:
        jpg_list = _glob('*.jpg')

        if len(jpg_list) > 0:

            # Create timelapse
            if include_timelapse:
                try:
                    logger.debug('Creating timelapse for {}'.format(dir_name))
                    video_file = make_timelapse(dir_name, overwrite=timelapse_overwrite)
                    logger.debug('Timelapse created: {}'.format(video_file))
                except Exception as e:
                    logger.debug("Problem creating timelapse: {}".format(e))

            # Remove jpgs
            if remove_jpgs:
                logger.debug('Removing jpgs')
                for f in jpg_list:
                    with suppress(OSError):
                        os.remove(f)
    except Exception as e:
        logger.warning('Problem with cleanup creating timelapse: {!r}'.format(e))


def main(directory,
         upload=False,
         remove_jpgs=False,
         overwrite=False,
         make_timelapse=False,
         **kwargs):
    """Upload images from the given directory.

    See argparse help string below for details about parameters.
    """

    pan_id = get_config('pan_id', default=None)
    if pan_id is None:
        raise error.GoogleCloudError("Can't upload without a valid pan_id in the config")

    logger.debug("Cleaning observation directory: {}".format(directory))
    try:
        clean_observation_dir(directory,
                              remove_jpgs=remove_jpgs,
                              include_timelapse=make_timelapse,
                              timelapse_overwrite=overwrite,
                              **kwargs)
    except Exception as e:
        raise error.PanError('Cannot clean observation dir: {}'.format(e))

    if upload:
        logger.debug("Uploading to storage bucket")

        try:
            upload_observation_to_bucket(
                pan_id,
                directory,
                include_files='*',
                exclude_files='upload_manifest.log',
                **kwargs)
        except Exception as e:
            logger.error(f'Error in uploading observations: {e!r}')

    return directory


if __name__ == '__main__':

    import argparse

    parser = argparse.ArgumentParser(description="Uploader for image directory")
    parser.add_argument('--directory', default=None,
                        help='Directory to be cleaned and uploaded.')
    parser.add_argument('--upload', default=False, action='store_true',
                        help='If images should be uploaded, default False.')
    parser.add_argument('--remove-jpgs', default=False, action='store_true',
                        help='If images should be removed after making timelapse, default False.')
    parser.add_argument('--make-timelapse', action='store_true', default=False,
                        help='Create a timelapse from the jpgs (requires ffmpeg), default False.')
    parser.add_argument('--overwrite', action='store_true', default=False,
                        help='Overwrite any existing files (such as timelapse), default False.')
    parser.add_argument('--verbose', action='store_true', default=False, help='Verbose.')

    args = parser.parse_args()

    if not os.path.exists(args.directory):
        print("Directory does not exist:", args.directory)

    clean_dir = main(**vars(args))
    print("Done cleaning for", clean_dir)
