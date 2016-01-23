#!/usr/bin/env python
# Licensed under a 3-clause BSD style license - see LICENSE.rst

import glob
import os
import sys


try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup
from panoptes.version import version

srcdir = os.path.dirname(__file__)

from distutils.command.build_py import build_py

# Get some values from the setup.cfg
from distutils import config
conf = config.ConfigParser()
conf.read(['setup.cfg'])
metadata = dict(conf.items('metadata'))

PACKAGENAME = metadata.get('package_name', 'packagename')
DESCRIPTION = metadata.get('description', '')
AUTHOR = metadata.get('author', '')
AUTHOR_EMAIL = metadata.get('author_email', '')
LICENSE = metadata.get('license', 'unknown')
URL = metadata.get('url', 'http://projectpanoptes.org')
KEYWORDS = metadata.get('keywords', 'Project PANOPTES')

# Get the long description from the package's docstring
__import__(PACKAGENAME)
package = sys.modules[PACKAGENAME]
LONG_DESCRIPTION = package.__doc__

# Treat everything in scripts except README.rst as a script to be installed
scripts = [fname for fname in glob.glob(os.path.join('scripts', '*'))
           if os.path.basename(fname) != 'README.rst']

setup(name=PACKAGENAME,
      version=version,
      description=DESCRIPTION,
      install_requires=['astropy'],
      author=AUTHOR,
      author_email=AUTHOR_EMAIL,
      license=LICENSE,
      url=URL,
      long_description=LONG_DESCRIPTION,
      zip_safe=False,
      use_2to3=True,
      keywords=KEYWORDS,
      scripts=['scripts/cr2_to_jpg.sh'],
      install_requires=['numpy>=1.7'],
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
