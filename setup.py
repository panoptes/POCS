#!/usr/bin/env python

from __future__ import print_function
from setuptools import setup, find_packages
import io
import codecs
import os
import sys

import panoptes

here = os.path.abspath(os.path.dirname(__file__))


def read(*filenames, **kwargs):
    encoding = kwargs.get('encoding', 'utf-8')
    sep = kwargs.get('sep', '\n')
    buf = []
    for filename in filenames:
        with io.open(filename, encoding=encoding) as f:
            buf.append(f.read())
    return sep.join(buf)

long_description = read('README.txt', 'CHANGES.txt')

setup(
    name='Panoptes',
    version=panoptes.__version__,
    url='https://github.com/panoptes/POCS',
    author='Project Panoptes',
    author_email='info@projectpanoptes.org',
    description='Panoptic Astronomical Networked OPtical observatory for Transiting Exoplanets Survey',
    long_description=long_description,
    packages=['panoptes'],
    include_package_data=True,
    platforms='any',
)
