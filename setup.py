#!/usr/bin/env python
# Licensed under an MIT style license - see LICENSE.txt

from setuptools import setup, find_namespace_packages

import itertools

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
    'google': [
        'gcloud',
        'google-cloud-storage',
    ],
    'mongo': [
        'pymongo>=3.2.2',
    ],
    'dev': [
        'jupyter-console',
        'jupyterlab',
    ],
    'required': [
        'astroplan>=0.6',
        'astropy>=4.0.0',
        'dateparser',
        'matplotlib',
        'numpy',
        'pandas',
        'panoptes-utils',
        'photutils',
        'pyserial>=3.1.1',
        'python_dateutil',
        'PyYAML>=5.1',
        'pyzmq<18.0.0',
        'readline',
        'requests',
        'scipy',
        'transitions',
    ],
    'social': [
        'tweepy',
    ],
    'testing': [
        'codecov',
        'coverage',
        'coveralls',
        'mocket',
        'pycodestyle==2.3.1',
        'pytest>=3.6',
        'pytest-cov',
        'pytest-remotedata>=0.3.1'
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
      # List additional groups of dependencies here (e.g. development
      # dependencies). You can install these using the following syntax,
      # for example:
      # $ pip install -e .[dev,test]
      install_requires=modules['required'],
      scripts=[
          'bin/pocs_shell',
          'bin/peas_shell',
      ],
      extras_require={
          'google': modules['google'],
          'mongo': modules['mongo'],
          'dev': modules['dev'],
          'social': modules['social'],
          'testing': modules['testing'],
          'all': list(set(itertools.chain.from_iterable(modules.values())))
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
