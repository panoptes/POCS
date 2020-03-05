#!/usr/bin/env python
# Licensed under an MIT style license - see LICENSE.txt

from setuptools import setup, find_namespace_packages

from configparser import ConfigParser
from distutils.command.build_py import build_py

from pocs.version import __version__

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

modules = {
    'required': [
        'astroplan>=0.6',
        'astropy>=4.0.0',
        'matplotlib',
        'numpy',
        'pandas',
        'panoptes-utils>=0.2.0',
        'pyserial>=3.1.1',
        'PyYAML>=5.1',
        'readline',
        'responses',
        'requests',
        'scipy',
        'transitions',
    ],
    'testing': [
        'codecov',
        'coverage',
        'coveralls',
        'mocket',
        'pycodestyle==2.3.1',
        'pytest>=3.6',
        'pytest-cov',
        'pytest-remotedata>=0.3.1',
        'responses'
    ],
}

setup(name=PACKAGENAME,
      version=__version__,
      description=DESCRIPTION,
      long_description=LONG_DESCRIPTION,
      author=AUTHOR,
      author_email=AUTHOR_EMAIL,
      license=LICENSE,
      url=URL,
      keywords=KEYWORDS,
      python_requires='>=3.6',
      setup_requires=['pytest-runner'],
      tests_require=modules['testing'],
      install_requires=modules['required'],
      scripts=[
          'bin/pocs',
          'bin/pocs-shell',
          'bin/peas-shell',
      ],
      extras_require={
          'testing': modules['testing'],
      },
      packages=find_namespace_packages(exclude=['tests', 'test_*']),
      classifiers=[
          'Development Status :: 3 - Alpha',
          'Environment :: Console',
          'Intended Audience :: Science/Research',
          'License :: OSI Approved :: MIT License',
          'Operating System :: POSIX',
          'Programming Language :: C',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.4',
          'Programming Language :: Python :: 3.5',
          'Programming Language :: Python :: 3.6',
          'Programming Language :: Python :: 3 :: Only',
          'Topic :: Scientific/Engineering :: Astronomy',
          'Topic :: Scientific/Engineering :: Physics',
      ],
      cmdclass={'build_py': build_py}
      )
