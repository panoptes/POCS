#!/usr/bin/env python

setup(
    name='Panoptes',
    version='0.0.1',
    packages=['Panoptes']
)

from __future__ import print_function
from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand
import io
import codecs
import os
import sys

import sandman

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

class PyTest(TestCommand):
    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        import pytest
        errcode = pytest.main(self.test_args)
        sys.exit(errcode)

setup(
    name='Panoptes',
    version=panoptes.__version__,
    url='https://github.com/panoptes/POCS',
    author='Project Panoptes',
    tests_require=['pytest'],
    install_requires=[],
    cmdclass={'test': PyTest},
    author_email='info@projectpanoptes.org',
    description='Panoptic Astronomical Networked OPtical observatory for Transiting Exoplanets Survey',
    long_description=long_description,
    packages=['panoptes'],
    include_package_data=True,
    platforms='any',
    test_suite='panoptes.test.test_panoptes',
    extras_require={
        'testing': ['pytest'],
    }
)