#!/usr/bin/env python3

import subprocess
import warnings
import shutil

from datetime import datetime as dt


def main(start_date=None, end_date=None, database=None, collections=list(), verbose=False):
    me_cmd = shutil.which('mongoexport')
    assert me_cmd, warnings.warn("No mongoexport command found!")

    if start_date is None:
        start_dt = dt.utcnow()
    else:
        start_dt = dt.strptime('{} 23:59:59'.format(start_date), '%Y%m%dUT %H:%M:%S')

    if end_date is None:
        end_dt = start_dt
    else:
        end_dt = dt.strptime('{} 23:59:59'.format(end_date), '%Y%m%dUT %H:%M:%S')

    start = dt(start_dt.year, start_dt.month, start_dt.day, 0, 0, 0, 0)
    end = dt(end_dt.year, end_dt.month, end_dt.day, 23, 59, 59, 0)

    date_query = '{"date": {"$gte": "' + start.isoformat() + '", "$lte": "' + end.isoformat() + '"}})'

    for collection in collections:
        out_file = '/var/panoptes/backup/{}_{}.json'.format(collection, start_date)
        export_cmd = [me_cmd, '--quiet', '-d', database, '-c', collection, '-q', date_query, '--out', out_file]

        if verbose:
            print("Exporting {}".format(collection))
            print("Cmd {}".format(export_cmd))
        subprocess.run(export_cmd)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="Make a plot of the weather for a give date.")

    parser.add_argument("-s", "--start-date", type=str, dest="start_date", default=None,
                        help="Starting UT Date to plot. If no end-date is provided plots entire date")
    parser.add_argument("-e", "--end-date", type=str, dest="end_date", default=None,
                        help="Ending UT Date to plot, defaults to None, causing start-date to plot entire day.")
    parser.add_argument('-d', '--database', type=str, dest='database',
                        default='panoptes', help="Mongo db to use for export.")
    parser.add_argument('-c', '--collections', type=str, nargs='+',
                        dest='collections', help="Collections to export. One file per collection will be generated.")
    parser.add_argument("-v", "--verbose", action="store_true", dest="verbose", default=False, help="Be verbose.")

    args = parser.parse_args()

    if args.end_date is not None:
        assert args.start_date is not None, warnings.warn("Can't use an end date without a start date")

    main(**vars(args))
