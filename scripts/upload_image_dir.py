#!/usr/bin/env python
import subprocess

from astropy.time import Time
from astropy import units as u
from astropy.utils import console
from pprint import pprint

from pocs.utils.database import PanMongo
from pocs.utils import current_time


def main(date, auto_confirm=False):
    db = PanMongo()

    seq_ids = db.observations.distinct(
        'sequence_id', {'date': {'$gte': Time(date).datetime}})
    imgs = [record['data']['file_path'] for record in db.observations.find(
        {'sequence_id': {'$in': seq_ids}}, {'data.file_path': 1})]

    dirs = set([img[0:img.rindex('/') - 1].replace('/var/panoptes/images/fields/', '')
                for img in imgs])

    if auto_confirm is False:
        print("Found the following dirs for {}:".format(date))
        pprint(dirs)
        if input("Proceed (Y/n): ") == 'n':
            return

    for d in console.ProgressBar(dirs):
        run_cmd = ['gsutil', '-mq', 'cp', '-r', '/var/panoptes/images/fields/{}/*.fz'.format(d),
                   'gs://panoptes-survey/PAN001/{}/'.format(d)]

        try:
            completed_process = subprocess.run(run_cmd, stdout=subprocess.PIPE)

            if completed_process.returncode != 0:
                print("Problem uploading")
                print(completed_process.stdout)
        except Exception as e:
            print("Problem uploading: {}".format(e))


if __name__ == '__main__':

    import argparse

    parser = argparse.ArgumentParser(
        description="Uploader for image directory")
    parser.add_argument('--date', default=None,
                        help='Export start date, e.g. 2016-01-01, defaults to yesterday')
    parser.add_argument('--auto-confirm', action='store_true', default=False,
                        help='Auto-confirm upload')

    args = parser.parse_args()
    if args.date is None:
        args.date = (current_time() - 1. * u.day).isot
    else:
        args.date = Time(args.date)

    main(**vars(args))
