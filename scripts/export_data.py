#!/usr/bin/env python3

import warnings
from astropy.utils import console

from pocs.utils.database import PanMongo
from pocs.utils.google.storage import PanStorage


def main(unit_id=None, upload=True, bucket='unit_sensors', **kwargs):
    assert unit_id is not None, warnings.warn("Must supply PANOPTES unit id, e.g. PAN001")

    console.color_print('Connecting to mongo')
    db = PanMongo()

    console.color_print('Exporting data')
    archived_files = db.export(**kwargs)

    if upload:
        storage = PanStorage(unit_id=unit_id, bucket=bucket)
        console.color_print("Uploading files:")

        for f in archived_files:
            r_fn = storage.upload(f)
            console.color_print("\t{:40s}".format(f), 'green', "\t->\t", 'red', r_fn, 'blue')


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="Make a plot of the weather for a give date.")

    parser.add_argument('unit_id', help="PANOPTES unit id, e.g. PAN001")
    parser.add_argument('-y', '--yesterday', action="store_true", dest='yesterday', default=True,
                        help="Yeserday\'s data, defaults to True if start-date is not provided, False otherwise.")
    parser.add_argument("-s", "--start-date", type=str, dest="start_date", default=None,
                        help="[yyyy-mm-dd] Start date, defaults to None; if provided, yesterday is ignored.")
    parser.add_argument("-e", "--end-date", type=str, dest="end_date", default=None,
                        help="[yyyy-mm-dd] End date, defaults to None, causing start-date to exports full day.")
    parser.add_argument('-d', '--database', type=str, dest='database',
                        default='panoptes', help="Mongo db to use for export, defaults to 'panoptes'")
    parser.add_argument('-c', '--collections', type=str, nargs='+', required=True,
                        dest='collections', help="Collections to export. One file per collection will be generated.")
    parser.add_argument('-b', '--bucket', help="Bucket for uploading data, defaults to unit_sensors.",
                        dest="bucket", default="unit_sensors")
    parser.add_argument('-z', '--gzip', help="Zip up json files, default True",
                        action="store_true", dest="gzip", default=True)
    parser.add_argument("-u", "--upload", action="store_true", dest="upload",
                        default=True, help="Upload to Google bucket.")
    parser.add_argument("-v", "--verbose", action="store_true", dest="verbose", default=False, help="Be verbose.")

    args = parser.parse_args()

    if args.end_date is not None:
        assert args.start_date is not None, warnings.warn("Can't use an end date without a start date")

    if args.start_date is not None:
        args.yesterday = False

    main(**vars(args))
