#!/usr/bin/env python3

import warnings

from panoptes.utils.database import PanMongo

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="Make a plot of the weather for a give date.")

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
    parser.add_argument('-z', '--gzip', help="Zip up json files", action="store_true", dest="gzip", default=False)
    parser.add_argument("-v", "--verbose", action="store_true", dest="verbose", default=False, help="Be verbose.")

    args = parser.parse_args()

    if args.end_date is not None:
        assert args.start_date is not None, warnings.warn("Can't use an end date without a start date")

    if args.start_date is not None:
        args.yesterday = False

    db = PanMongo()
    db.export(**vars(args))
