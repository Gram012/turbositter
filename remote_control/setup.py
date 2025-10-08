#!/usr/bin/env python

from distutils.core import setup
from setuptools import find_packages
import os

current_directory = os.path.dirname(os.path.abspath(__file__))

# read in a long description
try:
    with open(os.path.join(current_directory, "Reademe.md"), encoding='utf-8') as f:
        long_description = f.read()
except:
    long_description = ''


setup(name='remote_control',
      version='0.0.1',
      description='Remote control code for the TURBO project',
      author='Austin Korpi',
      author_email='korpi052@umn.edu',
      url='https://github.com/patkel/turbo_telescope',
      packages=find_packages(','),
      long_description=long_description,
      long_description_content_type='text/markdown',
      install_requires=["turbo_utils",
                        'numpy', 
                        'requests',
                        'scipy',
                        'regions',
                        'pympc',
                        'regex',
                        'scp',
                        'astropy',
                        'scikit-learn',
                        'gcn_kafka',
                        'astropy_healpix',
                        ] 
     )
