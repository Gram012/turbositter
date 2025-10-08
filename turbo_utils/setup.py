#!/usr/bin/env python

from distutils.core import setup
from setuptools import find_packages


setup(name='turbo_utils',
      version='0.0.1',
      description='Turbo Utility Functions',
      author='Austin Korpi',
      author_email='korpi052@umn.edu',
      url='https://github.com/patkel/turbo_telescope',
      packages=find_packages(','),
      long_description="Utility functions for turbo control and scheduling projects",
      long_description_content_type='text/markdown',
      install_requires=[] 
     )
