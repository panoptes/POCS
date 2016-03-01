#!/usr/bin/env python

import os
import warnings

import argparse

import shutil
import subprocess
import pandas as pd

from panoptes.utils import images


gsutil = shutil.which('gsutil')


def list_remote_dir(verbose=False):

    cmd = [gsutil, 'ls', REMOTE_PATH]

    if verbose:
        print(cmd)

    output = None

    try:
        output = subprocess.check_output(cmd, universal_newlines=True)
    except Exception as e:
        warnings.warn("Can't run command: {}".format(e))

    return output


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
        subprocess.call(cmd)
    except Exception as e:
        warnings.warn("Can't run command: {}".format(e))


def make_pec_data(name, obs_time, observer=None, verbose=False):

    image_dir = '{}/{}'.format(name, obs_time)

    data_table = images.get_pec_data(image_dir, observer=observer)

    if verbose:
        print(data_table.meta)

    hdf5_fn = '/var/panoptes/images/pec.hdf5'

    hdf5_path = 'observing/{}/{}'.format(data_table.meta['name'], data_table.meta['obs_date_start'])

    data_table.write(hdf5_fn, path=hdf5_path, append=True, serialize_meta=True, overwrite=True)


def main(remote=None, project=None, unit=None, **kwargs):

    # See if the remote path exists in the HDF5 data store
    store = pd.HDFStore(kwargs.get('hdf5_file'))

    hdf_path = 'observing/{}'.format(remote)

    if hdf_path not in store.keys():
        remote_path = 'gs://{}/{}/{}'.format(project, unit, remote)
        get_remote_dir(remote_path)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('remote', help='The remote directory to fetch.')
    parser.add_argument('--project', default='panoptes-survey', help='Project.')
    parser.add_argument('--unit', default='PAN001', help='The name of the unit.')
    parser.add_argument('--hdf5_file', default='/var/panoptes/images/pec.hdf5', help='HDF5 File')

    args = parser.parse_args()

    main(**vars(args))
