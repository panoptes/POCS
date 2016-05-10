#!/usr/bin/env python
# Licensed under a 3-clause BSD style license - see LICENSE.rst

import glob
import os

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

srcdir = os.path.dirname(__file__)

from distutils.command.build_py import build_py

AUTHOR = 'Wilfred T Gee'
AUTHOR_EMAIL = 'wtylergee@gmail.com'
DESCRIPTION = 'PANOPTES Environmental Analysis System'
KEYWORDS = 'PANOPTES'
LICENSE = 'MIT'
LONG_DESCRIPTION = DESCRIPTION
PACKAGENAME = 'peas'
URL = 'http://projectpanoptes.org'

# Treat everything in scripts except README.rst as a script to be installed
scripts = [fname for fname in glob.glob(os.path.join('scripts', '*'))
           if os.path.basename(fname) != 'README.rst']

setup(name=PACKAGENAME,
      version='0.0.1',
      description=DESCRIPTION,
      long_description=LONG_DESCRIPTION,
      author=AUTHOR,
      author_email=AUTHOR_EMAIL,
      license=LICENSE,
      url=URL,
      keywords=KEYWORDS,
      install_requires=['numpy>=1.10'],
      test_suite="panoptes.tests",
      classifiers=[
          'Development Status :: 3 - Alpha',
          'Environment :: Console',
          'Intended Audience :: Science/Research',
          'License :: OSI Approved :: MIT License',
          'Operating System :: POSIX',
          'Programming Language :: C',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.3',
          'Programming Language :: Python :: 3.4',
          'Programming Language :: Python :: 3.5',
          'Programming Language :: Python :: 3 :: Only',
          'Topic :: Scientific/Engineering :: Astronomy',
          'Topic :: Scientific/Engineering :: Physics',
      ],
      cmdclass={'build_py': build_py}
      )
