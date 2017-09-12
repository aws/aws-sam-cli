#!/usr/bin/env python
import os
from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
VERSION = open(os.path.join(here, 'VERSION')).read().strip()

required_eggs = [
    'requests>=2.18.4',
    'boto3>=1.4.7',
]

setup(
    name='example.cloudschedule',
    version=VERSION,
    description="",
    author="zerotired",
    author_email='andi@doppelpop.de',
    url='',
    packages=find_packages(exclude=["*.tests", "*.tests.*", "tests.*", "tests"]),
    # http://pythonhosted.org/distribute/setuptools.html#namespace-packages
    namespace_packages=['example'],
    # TODO amb
    # include_package_data=True,
    package_data={'example': ['static/*.*', 'templates/*.*']},
    install_requires=required_eggs,
    extras_require=dict(
        test=required_eggs + [
            'pytest>=3.2',
        ],
        develop=required_eggs + [
            'ipdb>=0.10.2',
        ]),
    zip_safe=False,
    entry_points={
        'console_scripts': [
            'index=example.schedule:lambda_sandbox_down_handler'
        ],
    },
    dependency_links=[
    ],
)
