import argparse
import os
import shutil

from astroplan import download_IERS_A
from astropy.utils import data


def download_all_files(data_folder=None, wide_field=True, narrow_field=False):
    download_IERS_A()

    if data_folder is None:
        data_folder = "{}/astrometry/data".format(os.getenv('PANDIR'))

    def download_one_file(fn):
        dest = "{}/{}".format(data_folder, os.path.basename(fn))
        if not os.path.exists(dest):
            url = "http://data.astrometry.net/{}".format(fn)
            df = data.download_file(url)
            try:
                shutil.move(df, dest)
            except OSError as e:
                print("Problem saving. (Maybe permissions?): {}".format(e))

    if wide_field:
        for i in range(4110, 4119):
            download_one_file('4100/index-{}.fits'.format(i))

    if narrow_field:
        for i in range(4210, 4219):
            download_one_file('4200/index-{}.fits'.format(i))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument('--folder', help='Folder to place astrometry data')

    args = parser.parse_args()

    if args.folder and not os.path.exists(args.folder):
        print("{} does not exist.".format(args.folder))

    download_all_files(data_folder=args.folder)
