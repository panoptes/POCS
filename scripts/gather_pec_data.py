#!/usr/bin/env python

import os
import warnings

import shutil
import subprocess

from panoptes.utils import images


MACHINE='PAN001'
PROJECT = 'panoptes-survey'
REMOTE_PATH = 'gs://{}/{}'.format(PROJECT, MACHINE)
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


if __name__ == '__main__':
    print(list_remote_dir())
