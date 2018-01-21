#!/usr/bin/env python
import os
import subprocess

from warnings import warn
from astropy import units as u
from astropy.time import Time
from astropy.utils import console
from pprint import pprint

from pocs.utils.database import PanMongo
from pocs.utils import current_time
from pocs.utils.config import load_config


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
        pan_id = config['PAN_ID']
    except KeyError:
        warn("Can't upload without a valid PAN_ID")
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
        img_path = '{}/{}/*.fz'.format(fields_dir, d)
        remote_path = '{}/{}/'.format(pan_id, d).replace('//', '/')
        bucket = 'gs://panoptes-survey/'
        run_cmd = ['gsutil', '-mq', 'cp', '-r', img_path, bucket + remote_path]

        try:
            completed_process = subprocess.run(run_cmd, stdout=subprocess.PIPE)

            if completed_process.returncode != 0:
                warn("Problem uploading")
                warn(completed_process.stdout)
        except Exception as e:
            warn("Problem uploading: {}".format(e))

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
