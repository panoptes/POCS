#!/usr/bin/env python
import os

from panoptes.utils.config import load_config
from panoptes.utils.images import clean_observation_dir
from panoptes.utils.google.storage import upload_observation_to_bucket
from panoptes.utils import error


def main(directory,
         upload=False,
         remove_jpgs=False,
         overwrite=False,
         make_timelapse=False,
         verbose=False,
         **kwargs):
    """Upload images from the given directory.

    See argparse help string below for details about parameters.
    """

    def _print(msg):
        if verbose:
            print(msg)

    config = load_config()
    try:
        pan_id = config['pan_id']
    except KeyError:
        raise error.GoogleCloudError("Can't upload without a valid pan_id in the config")

    _print("Cleaning observation directory: {}".format(directory))
    try:
        clean_observation_dir(directory,
                              remove_jpgs=remove_jpgs,
                              include_timelapse=make_timelapse,
                              timelapse_overwrite=overwrite,
                              verbose=verbose,
                              **kwargs)
    except Exception as e:
        raise error.PanError('Cannot clean observation dir: {}'.format(e))

    if upload:
        _print("Uploading to storage bucket")

        upload_observation_to_bucket(
            pan_id,
            directory,
            include_files='*',
            exclude_files='upload_manifest.log',
            verbose=verbose, **kwargs)

    return directory


if __name__ == '__main__':

    import argparse

    parser = argparse.ArgumentParser(description="Uploader for image directory")
    parser.add_argument('--directory', default=None,
                        help='Directory to be cleaned and uploaded.')
    parser.add_argument('--upload', default=False, action='store_true',
                        help='If images should be uploaded, default False.')
    parser.add_argument('--remove_jpgs', default=False, action='store_true',
                        help='If images should be removed after making timelapse, default False.')
    parser.add_argument('--make_timelapse', action='store_true', default=False,
                        help='Create a timelapse from the jpgs (requires ffmpeg), default False.')
    parser.add_argument('--overwrite', action='store_true', default=False,
                        help='Overwrite any existing files (such as timelapse), default False.')
    parser.add_argument('--verbose', action='store_true', default=False, help='Verbose.')

    args = parser.parse_args()

    if not os.path.exists(args.directory):
        print("Directory does not exist:", args.directory)

    clean_dir = main(**vars(args))
    if args.verbose:
        print("Done cleaning for", clean_dir)
