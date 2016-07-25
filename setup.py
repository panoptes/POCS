#!/usr/bin/env python
# Licensed under an MIT style license - see LICENSE.txt

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

from configparser import ConfigParser
from distutils.command.build_py import build_py

from pocs.version import version

# Get some values from the setup.cfg
conf = ConfigParser()
conf.read(['setup.cfg'])
metadata = dict(conf.items('metadata'))

AUTHOR = metadata.get('author', '')
AUTHOR_EMAIL = metadata.get('author_email', '')
DESCRIPTION = metadata.get('description', '')
KEYWORDS = metadata.get('keywords', 'Project PANOPTES')
LICENSE = metadata.get('license', 'unknown')
LONG_DESCRIPTION = metadata.get('long_description', '')
PACKAGENAME = metadata.get('package_name', 'packagename')
URL = metadata.get('url', 'http://projectpanoptes.org')

# Treat everything in scripts except README.rst as a script to be installed
# scripts = [fname for fname in glob.glob(os.path.join('scripts', '*'))
#            if os.path.basename(fname) != 'README.rst']

setup(name=PACKAGENAME,
      version=version,
      description=DESCRIPTION,
      long_description=LONG_DESCRIPTION,
      author=AUTHOR,
      author_email=AUTHOR_EMAIL,
      license=LICENSE,
      url=URL,
      keywords=KEYWORDS,
      # scripts=['scripts/cr2_to_jpg.sh'],
      install_requires=['numpy>=1.10', 'astropy', 'transitions', 'astroplan'],
      setup_requires=['pytest-runner'],
      tests_require=['pytest'],
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
