#!/usr/bin/env python

from __future__ import print_function
from setuptools import setup, find_packages
import io
import codecs
import os
import sys

import panoptes

version = '0.0.1'

here = os.path.abspath(os.path.dirname(__file__))

def read(*filenames, **kwargs):
    encoding = kwargs.get('encoding', 'utf-8')
    sep = kwargs.get('sep', '\n')
    buf = []
    for filename in filenames:
        with io.open(filename, encoding=encoding) as f:
            buf.append(f.read())
    return sep.join(buf)

long_description = read('README.md', 'CHANGES.txt')

setup(
    name='Panoptes',
    version=version,
    url='https://github.com/panoptes/POCS',
    author='Project Panoptes',
    install_requires=[],
    author_email='info@projectpanoptes.org',
    description='Panoptic Astronomical Networked OPtical observatory for Transiting Exoplanets Survey',
    long_description=long_description,
    packages = find_packages(),
    include_package_data=True,
    platforms='any',
)
