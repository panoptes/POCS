#!/usr/bin/env python
import os

from warnings import warn
from glob import glob
from astropy.io import fits

from pocs.utils.config import load_config
from pocs.utils.images import clean_observation_dir
from pocs.utils.google.storage import upload_directory_to_bucket
from pocs.utils.google.clouddb import add_header_to_db


def main(directory, upload=True, send_headers=True, verbose=False):
    """Upload images from the given directory. """

    config = load_config()
    try:
        pan_id = config['pan_id']
    except KeyError:
        warn("Can't upload without a valid pan_id in the config")
        return

    def _print(msg):
        if verbose:
            print(msg)

    _print("Cleaning observation directory")
    clean_observation_dir(directory)

    if upload:
        _print("Uploading to storage bucket")
        upload_directory_to_bucket(pan_id, directory)

    if send_headers:
        _print("Sending FITS headers to metadb")
        for fn in glob(os.path.join(directory, '*.fz')):
            h0 = fits.getheader(fn, ext=1)
            add_header_to_db(h0)


if __name__ == '__main__':

    import argparse

    parser = argparse.ArgumentParser(description="Uploader for image directory")
    parser.add_argument('--directory', default=None, help='Directory to be cleaned and uploaded')
    parser.add_argument('--upload', default=True, action='store_true',
                        help='If images should be uploaded, default True')
    parser.add_argument('--send_headers', default=True, action='store_true',
                        help='If FITS headers should be sent to metadb, default True')
    parser.add_argument('--verbose', action='store_true', default=False, help='Verbose')

    args = parser.parse_args()

    assert os.path.exists(args.directory)

    num_uploads = main(**vars(args))
    if args.verbose:
        print("{} images uploaded".format(num_uploads))
