#!/usr/bin/env python
import os

from warnings import warn
from astropy import units as u
from astropy.time import Time
from astropy.utils import console
from pprint import pprint

from pocs.utils.database import PanMongo
from pocs.utils import current_time
from pocs.utils.config import load_config
from pocs.utils.images import upload_observation_dir


def main(date, auto_confirm=False, verbose=False):
    """Upload images more recent than given date

    Args:
        date (datetime): Images more recent than this date will be uploaded
        auto_confirm (bool, optional): If upload should first be confirm. Default
            to False.
        verbose (bool, optional): Verbose output. Default False.

    Returns:
        int: Number of images uploaded
    """
    db = PanMongo()
    config = load_config()
    try:
        pan_id = config['pan_id']
    except KeyError:
        warn("Can't upload without a valid pan_id in the config")
        return

    def _print(msg):
        if verbose:
            print(msg)

    img_dir = config['directories']['images']
    fields_dir = os.path.join(img_dir, 'fields')

    # Get all the sequences from previous day
    seq_ids = db.observations.distinct(
        'sequence_id', {'date': {'$gte': date}})
    # Find all images corresponding to those sequences
    imgs = [record['data']['file_path'] for record in db.observations.find(
        {'sequence_id': {'$in': seq_ids}}, {'data.file_path': 1})]

    # Get directory names without leading fields_dir and trailing image dir
    dirs = sorted(set([img[0:img.rindex('/') - 1].replace(fields_dir, '') for img in imgs]))

    if auto_confirm is False:
        _print("Found the following dirs for {}:".format(date))
        pprint(dirs)
        if input("Proceed (Y/n): ") == 'n':
            return

    if verbose:
        dir_iterator = console.ProgressBar(dirs)
    else:
        dir_iterator = dirs

    for d in dir_iterator:
        dir_name = '{}/{}'.format(fields_dir, d)

        upload_observation_dir(pan_id, dir_name)

    return len(imgs)


if __name__ == '__main__':

    import argparse

    parser = argparse.ArgumentParser(
        description="Uploader for image directory")
    parser.add_argument('--date', default=None,
                        help='Export start date, e.g. 2016-01-01, defaults to yesterday')
    parser.add_argument('--auto-confirm', action='store_true', default=False,
                        help='Auto-confirm upload, implies verbose.')
    parser.add_argument('--verbose', action='store_true', default=False,
                        help='Verbose')

    args = parser.parse_args()

    if args.date is None:
        args.date = (current_time() - 1. * u.day).datetime
    else:
        args.date = Time(args.date).datetime

    if args.auto_confirm is False:
        args.verbose = True

    num_uploads = main(**vars(args))
    if args.verbose:
        print("{} images uploaded".format(num_uploads))
