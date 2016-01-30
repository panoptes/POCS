#!/usr/bin/env python

import sys
import os
import glob
from astropy.utils import console
import argparse

sys.path.append(os.getenv('POCS', '/var/panoptes/POCS'))

from panoptes.utils import images


parser = argparse.ArgumentParser(description='Convert Canon .cr2 file(s) to a FITS')
parser.add_argument('--directory', help="Convert all .cr2 files in directory.")
parser.add_argument('-v', '--verbose', action='store_true', default=False, help='Verbose mode')


def out(msg):
    if args.verbose:
        console.color_print(msg)


args = parser.parse_args()

if args.directory:
    out("Converting all files in {}".format(args.directory))
    cr2_files = glob.glob("{}/*.cr2".format(args.directory))

    with console.ProgressBarOrSpinner(len(cr2_files), "CR2 to FITS") as bar:
        for num, cr2 in enumerate(cr2_files):

            images.get_solve_field(cr2)

            bar.update(num)
