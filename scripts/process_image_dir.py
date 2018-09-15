#!/usr/bin/env python
import os

from warnings import warn
from glob import glob
from astropy.io import fits

from pocs.utils import current_time
from pocs.utils.config import load_config
from pocs.utils.images import clean_observation_dir
from pocs.utils.google.storage import upload_observation_to_bucket
from pocs.utils.google.clouddb import add_header_to_db


def main(directory, upload=True, remove_jpgs=False, send_headers=True, verbose=False, **kwargs):
    """Upload images from the given directory. """

    def _print(msg):
        if verbose:
            print(msg)

    config = load_config()
    try:
        pan_id = config['pan_id']
    except KeyError:
        warn("Can't upload without a valid pan_id in the config")
        return

    _print("Cleaning observation directory: {}".format(directory))
    try:
        clean_observation_dir(directory, remove_jpgs=remove_jpgs, verbose=verbose, **kwargs)
    except FileExistsError as e:
        print(e)

    if upload:
        _print("Uploading to storage bucket")

        uploaded_files_fn = os.path.join(directory, 'uploaded_files.txt')

        if os.path.exists(uploaded_files_fn):
            _print("Files have been uploaded already, skipping")
        else:
            file_search_path = upload_observation_to_bucket(
                pan_id,
                directory,
                include_files='*',
                verbose=verbose, **kwargs)
            uploaded_files = sorted(glob(file_search_path))
            with open(uploaded_files_fn, 'w') as f:
                f.write('# Files uploaded on {}\n'.format(current_time(pretty=True)))
                f.write('\n'.join(uploaded_files))

    if send_headers:
        _print("Sending FITS headers to metadb")
        for fn in glob(os.path.join(directory, '*.fz')):
            h0 = fits.getheader(fn, ext=1)
            add_header_to_db(h0)

    return directory


if __name__ == '__main__':

    import argparse

    parser = argparse.ArgumentParser(description="Uploader for image directory")
    parser.add_argument('--directory', default=None,
                        help='Directory to be cleaned and uploaded')
    parser.add_argument('--upload', default=False, action='store_true',
                        help='If images should be uploaded, default False')
    parser.add_argument('--send_headers', default=False, action='store_true',
                        help='If FITS headers should be sent to metadb, default False')
    parser.add_argument('--remove_jpgs', default=False, action='store_true',
                        help='If images should be removed after making timelapse, default False')
    parser.add_argument('--overwrite', action='store_true', default=False,
                        help='Overwrite any existing files (such as the timelapse), default False')
    parser.add_argument('--verbose', action='store_true', default=False, help='Verbose')

    args = parser.parse_args()

    if not os.path.exists(args.directory):
        print("Directory does not exist:", args.directory)

    clean_dir = main(**vars(args))
    if args.verbose:
        print("Done cleaning for", clean_dir)
