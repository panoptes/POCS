#!/usr/bin/env python
import os
import sys

from glob import glob
from astropy.io import fits

from pocs.utils.config import load_config
from pocs.utils.images import clean_observation_dir
from pocs.utils.google.storage import upload_observation_to_bucket
from pocs.utils.db.postgres import get_db_proxy_conn
from pocs.utils.db.postgres import add_header_to_db
from pocs.utils import error


def main(directory,
         upload=False,
         remove_jpgs=False,
         send_headers=False,
         db_pass=None,
         verbose=False,
         **kwargs):
    """Upload images from the given directory. """

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
        clean_observation_dir(directory, remove_jpgs=remove_jpgs, verbose=verbose, **kwargs)
    except Exception as e:
        raise error.PanError('Cannot clean observation dir: {}'.format(e))

    if upload:
        _print("Uploading to storage bucket")

        upload_observation_to_bucket(
            pan_id,
            directory,
            include_files='*',
            verbose=verbose, **kwargs)

    if send_headers:
        _print("Making connection to Meta DB")
        metadb_conn = get_db_proxy_conn(db_pass=db_pass)
        for fn in glob(os.path.join(directory, '*.fz')):
            _print("Sending FITS header: {}".format(fn))
            h0 = fits.getheader(fn, ext=1)
            try:
                add_header_to_db(h0, conn=metadb_conn)
            except Exception as e:
                _print("Problem with fits header: {}".format(e))

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
    parser.add_argument('--db_pass', help='Password for the metadb user')
    parser.add_argument('--remove_jpgs', default=False, action='store_true',
                        help='If images should be removed after making timelapse, default False')
    parser.add_argument('--overwrite', action='store_true', default=False,
                        help='Overwrite any existing files (such as the timelapse), default False')
    parser.add_argument('--verbose', action='store_true', default=False, help='Verbose')

    args = parser.parse_args()

    if not os.path.exists(args.directory):
        print("Directory does not exist:", args.directory)

    if not args.db_pass:
        try:
            args.db_pass = os.environ['METADB_PASS']
        except KeyError:
            pass

    if args.send_headers and not args.db_pass:
        print("No password set for the CloudSQL database (METADB_PASS), exiting.")
        sys.exit(1)

    clean_dir = main(**vars(args))
    if args.verbose:
        print("Done cleaning for", clean_dir)
