# Downloads IERS Bulletin A (Earth Orientation Parameters, used by astroplan)
# and astrometry.net indices.

import argparse
import os
import shutil
import warnings


def _suppress_IERS_A_warning(message, *args, **kwargs):
    if 'OldEarthOrientationDataWarning' in message or 'download_IERS_A' in message:
        return
    _suppress_IERS_A_warning.original(message, *args, **kwargs)


try:
    _suppress_IERS_A_warning.original = warnings.warn
    warnings.warn = _suppress_IERS_A_warning
    from astroplan import download_IERS_A
    from astropy.utils import data
finally:
    warnings.warn = _suppress_IERS_A_warning.original


def _default_data_folder():
    return "{}/astrometry/data".format(os.getenv('PANDIR'))


class Downloader:
    """Downloads IERS Bulletin A and astrometry.net indices.

    IERS Bulletin A contains rapid determinations for earth orientation
    parameters, and is used by astroplan. Learn more at: https://www.iers.org

    Astrometry.net provides indices used to 'plate solve', i.e. to determine
    which stars are in an arbitrary image of the night sky.
    """

    def __init__(self, data_folder=None, wide_field=True, narrow_field=False, keep_going=True):
        """
        Args:
            data_folder: Path to directory into which to copy the astrometry.net indices.
            wide_field: If true, downloads wide field astrometry.net indices.
            narrow_field: If true, downloads narrow field astrometry.net indices.
            keep_going: If False, exceptions are not suppressed. If True, returns False if there
                are any download failures, else returns True.
        """
        self.data_folder = data_folder or _default_data_folder()
        self.wide_field = wide_field
        self.narrow_field = narrow_field
        self.keep_going = keep_going

    def download_all_files(self):
        """Downloads the files according to the attributes of this object."""
        result = True
        try:
            download_IERS_A()
        except Exception as e:
            if not self.keep_going:
                raise e
            print('Failed to download IERS A bulletin: {}'.format(e))
            result = False
        if self.wide_field:
            for i in range(4110, 4119):
                if not self.download_one_file('4100/index-{}.fits'.format(i)):
                    result = False
        if self.narrow_field:
            for i in range(4210, 4219):
                if not self.download_one_file('4200/index-{}.fits'.format(i)):
                    result = False
        return result

    def download_one_file(self, fn):
        """Downloads one astrometry.net file into self.data_folder."""
        dest = "{}/{}".format(self.data_folder, os.path.basename(fn))
        if os.path.exists(dest):
            return True
        url = "http://data.astrometry.net/{}".format(fn)
        try:
            df = data.download_file(url)
        except Exception as e:
            if not self.keep_going:
                raise e
            print('Failed to download {}: {}'.format(url, e))
            return False
        try:
            shutil.move(df, dest)
            return True
        except OSError as e:
            if not self.keep_going:
                raise e
            print("Problem saving {}. Check permissions: {}".format(url, e))
            return False


def download_all_files(data_folder=None, wide_field=True, narrow_field=False, keep_going=True):
    dl = Downloader(
        data_folder=data_folder,
        keep_going=keep_going,
        narrow_field=narrow_field,
        wide_field=wide_field)
    return dl.download_all_files()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        '--folder',
        help=('Destination folder for astrometry indices. Default: {}'.format(
            _default_data_folder())),
        default=_default_data_folder())

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        '--keep_going',
        action='store_true',
        help='Ignore download failures and keep going to the other downloads (default)')
    group.add_argument(
        '--nokeep_going', action='store_true', help='Fail immediately if any download fails')

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        '--narrow_field', action='store_true', help='Do download narrow field indices')
    group.add_argument(
        '--nonarrow_field',
        action='store_true',
        help='Skip downloading narrow field indices (default)')

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        '--wide_field', action='store_true', help='Do download wide field indices (default)')
    group.add_argument(
        '--nowide_field', action='store_true', help='Skip downloading wide field indices')

    args = parser.parse_args()

    if args.folder and not os.path.exists(args.folder):
        print("Warning, data folder {} does not exist.".format(args.folder))

    download_all_files(
        data_folder=args.folder,
        keep_going=args.keep_going or not args.nokeep_going,
        narrow_field=args.narrow_field,
        wide_field=args.wide_field or not args.nowide_field)
