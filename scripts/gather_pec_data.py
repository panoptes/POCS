#!/usr/bin/env python

import os
import sys
import warnings

import argparse

import shutil
import subprocess
import pandas as pd

from panoptes import Panoptes
from panoptes.utils import images

from astropy.utils.data import get_file_contents

gsutil = shutil.which('gsutil')


def list_remote_dir(prefix=None, verbose=False):

    if prefix is not None:
        rp = '{}/{}'.format(REMOTE_PATH, prefix)
    else:
        rp = REMOTE_PATH

    cmd = [gsutil, 'ls', rp]

    if verbose:
        print(cmd)

    output = None

    try:
        output = subprocess.run(cmd, stdout=subprocess.PIPE, check=True, universal_newlines=True)
    except Exception as e:
        warnings.warn("Can't run command: {}".format(e))

    return output.stdout.strip()


def get_remote_dir(remote_dir, verbose=False):

    full_dir = '/var/panoptes/images/fields/{}/'.format(remote_dir.rstrip('/').split('/')[-2])

    gsutil = shutil.which('gsutil')

    cmd = [gsutil, '-m', 'cp', '-r', remote_dir, full_dir]

    if verbose:
        print(cmd)

    try:
        os.mkdir(full_dir)
    except OSError as e:
        warnings.warn("Can't create dir: {}".format(e))

    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, check=True)
    except Exception as e:
        warnings.warn("Can't run command: {}".format(e))
        sys.exit(1)

    return full_dir


def make_pec_data(image_dir, observer=None, verbose=False):

    name, obs_time = image_dir.rstrip('/').split('/')

    data_table = images.get_pec_data(image_dir, observer=observer)

    if verbose:
        print(data_table.meta)

    hdf5_fn = '/var/panoptes/images/pec.hdf5'

    hdf5_path = 'observing/{}/{}'.format(data_table.meta['name'], data_table.meta['obs_date_start'])

    data_table.write(hdf5_fn, path=hdf5_path, append=True, serialize_meta=True, overwrite=True)


def main(remote=None, project=None, unit=None, folders_file=None, verbose=False, **kwargs):

    pan = Panoptes(simulator=['all'])

    folders = get_file_contents(folders_file).strip().split('\n')

    # See if the remote path exists in the HDF5 data store
    store = pd.HDFStore(kwargs.get('hdf5_file'))

    for folder in folders:
        folder = folder.rstrip('/')

        hdf_path = '/observing/{}'.format(folder)

        if hdf_path not in store.keys():
            remote_path = 'gs://{}/{}/{}'.format(project, unit, folder)

            # Get the data
            local_dir = get_remote_dir(remote_path)

            # Make data
            make_pec_data(folder, observer=pan.observatory.scheduler)

            # Remove the data
            try:
                shutil.rmtree(local_dir)
                rm_cmd = ['rm', '/tmp/tmp.sanitized.*']  # FITS conversion files
                subprocess.run(rm_cmd, check=True, stdout=subprocess.PIPE)
            except Exception as e:
                if verbose:
                    print("Error removing dir: {}".format(e))
        else:
            if verbose:
                print("{} already in HDF5 table".format(folder))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('folders_file', help='List of remote dirs')
    parser.add_argument('--project', default='panoptes-survey', help='Project.')
    parser.add_argument('--unit', default='PAN001', help='The name of the unit.')
    parser.add_argument('--hdf5_file', default='/var/panoptes/images/pec.hdf5', help='HDF5 File')

    args = parser.parse_args()

    if not os.path.exists(args.folders_file):
        print("{} does not exist.".format(args.folders_file))

    main(**vars(args))
