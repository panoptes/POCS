#!/usr/bin/env python

import argparse

from panoptes.utils.images import create_timelapse


if __name__ == '__main__':

    parser = argparse.ArgumentParser(
        description='Create a timelapse from the images in a directory')
    parser.add_argument('--directory', help="Image directory.")
    parser.add_argument('-v', '--verbose', action='store_true',
                        default=False, help='Verbose mode')

    args = parser.parse_args()

    if args.directory:
        create_timelapse(args.directory)
