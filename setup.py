#!/usr/bin/env python

import io
import re
import os
from setuptools import setup, find_packages


def read(*filenames, **kwargs):
    encoding = kwargs.get("encoding", "utf-8")
    sep = kwargs.get("sep", os.linesep)
    buf = []
    for filename in filenames:
        with io.open(filename, encoding=encoding) as f:
            buf.append(f.read())
    return sep.join(buf)


def read_requirements(req="base.txt"):
    content = read(os.path.join("requirements", req))
    return [line for line in content.split(os.linesep) if not line.strip().startswith("#")]


def read_version():
    content = read(os.path.join(os.path.dirname(__file__), "samcli", "__init__.py"))
    return re.search(r"__version__ = \"([^']+)\"", content).group(1)


cmd_name = "sam"
if os.getenv("SAM_CLI_DEV"):
    # We are installing in a dev environment
    cmd_name = "samdev"

setup(
    name="aws-sam-cli",
    version=read_version(),
    description="AWS SAM CLI is a CLI tool for local development and testing of Serverless applications",
    long_description=read("README.md"),
    long_description_content_type="text/markdown",
    author="Amazon Web Services",
    author_email="aws-sam-developers@amazon.com",
    url="https://github.com/awslabs/aws-sam-cli",
    license="Apache License 2.0",
    packages=find_packages(exclude=["tests.*", "tests"]),
    keywords="AWS SAM CLI",
    # Support Python 3.6 or greater
    python_requires=">=3.6, <=4.0, !=4.0",
    entry_points={"console_scripts": ["{}=samcli.cli.main:cli".format(cmd_name)]},
    install_requires=read_requirements("base.txt"),
    extras_require={"dev": read_requirements("dev.txt")},
    include_package_data=True,
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Environment :: Other Environment",
        "Intended Audience :: Developers",
        "Intended Audience :: Information Technology",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Topic :: Internet",
        "Topic :: Software Development :: Build Tools",
        "Topic :: Utilities",
    ],
)
