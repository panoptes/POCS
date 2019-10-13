import os
import sys
import argparse
from panoptes.utils.data import Downloader

DEFAULT_DATA_FOLDER = "{}/astrometry/data".format(os.getenv('PANDIR'))


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        '--folder',
        help=f'Destination folder for astrometry indices. Default: {DEFAULT_DATA_FOLDER}',
        default=DEFAULT_DATA_FOLDER)

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        '--keep-going',
        action='store_true',
        help='Ignore download failures and keep going to the other downloads (default)')
    group.add_argument(
        '--no-keep-going', action='store_true', help='Fail immediately if any download fails')

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        '--narrow-field', action='store_true', help='Do download narrow field indices')
    group.add_argument(
        '--no-narrow-field',
        action='store_true',
        help='Skip downloading narrow field indices (default)')

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        '--wide-field', action='store_true', help='Do download wide field indices (default)')
    group.add_argument(
        '--no-wide-field', action='store_true', help='Skip downloading wide field indices')

    args = parser.parse_args()

    if args.folder and not os.path.exists(args.folder):
        print("Warning, data folder {} does not exist.".format(args.folder))

    keep_going = args.keep_going or not args.no_keep_going

    # --no_narrow_field is the default, so the the args list below ignores args.no_narrow_field.
    dl = Downloader(
        data_folder=args.folder,
        keep_going=keep_going,
        narrow_field=args.narrow_field,
        wide_field=args.wide_field or not args.no_wide_field)
    success = dl.download_all_files()

    # Docker builds are failing if one of the files is missing, which shouldn't
    # be the case. This will all need to be reworked as part of our IERS updates.
    if success is False and keep_going is True:
        success = True

    return success


if __name__ == '__main__':
    if not main():
        sys.exit(1)
