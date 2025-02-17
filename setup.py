#!/usr/bin/env python

import io
import re
import os
from setuptools import setup, find_packages


def read(*filenames, **kwargs):
    encoding = kwargs.get("encoding", "utf-8")
    # io.open defaults to \n as universal line ending no matter on what system
    sep = kwargs.get("sep", "\n")
    buf = []
    for filename in filenames:
        with io.open(filename, encoding=encoding) as f:
            buf.append(f.read())
    return sep.join(buf)


def read_requirements(req="base.txt"):
    content = read(os.path.join("requirements", req))
    requirements = list()
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("#"):
            continue
        elif line.startswith("-r"):
            requirements.extend(read_requirements(line[3:]))
        else:
            requirements.append(line)
    return requirements


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
    url="https://github.com/aws/aws-sam-cli",
    license="Apache License 2.0",
    packages=find_packages(exclude=["tests.*", "tests", "installer.*", "installer", "schema.*", "schema"]),
    keywords="AWS SAM CLI",
    # Support Python 3.9 or greater
    python_requires=">=3.9, <=4.0, !=4.0",
    entry_points={"console_scripts": ["{}=samcli.cli.main:cli".format(cmd_name)]},
    install_requires=read_requirements("base.txt"),
    extras_require={"pre-dev": read_requirements("pre-dev.txt"), "dev": read_requirements("dev.txt")},
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
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.11",
        "Topic :: Internet",
        "Topic :: Software Development :: Build Tools",
        "Topic :: Utilities",
    ],
)
