#!/usr/bin/env python

import os
from setuptools import setup, find_packages

# Function to parse requirements.txt
def parse_requirements(filename):
    requirements = []
    with open(filename, 'r') as file:
        for line in file:
            line = line.strip()
            # Skip empty lines, comments, or git URLs
            if line and not line.startswith('#') and not line.startswith('git+'):
                requirements.append(line)
    return requirements

# Get the directory of setup.py
setup_dir = os.path.dirname(os.path.realpath(__file__))
path_req = os.path.join(setup_dir, 'requirements.txt')

# Parse requirements
reqs = parse_requirements(path_req)

setup(
    name='pgoapi',
    author='tjado',
    description='Pokemon Go API lib',
    version='2.14.0',
    url='https://github.com/goedzo/pgoapi',
    download_url='https://github.com/pogodevorg/pgoapi/releases',
    packages=find_packages(),
    install_requires=reqs
)