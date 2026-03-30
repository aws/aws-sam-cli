#!/usr/bin/env python

import os
from setuptools import setup

# When SAM_CLI_DEV is set, register "samdev" as the console script instead of "sam".
# All other metadata (name, version, dependencies, etc.) is defined in pyproject.toml.
cmd_name = "samdev" if os.getenv("SAM_CLI_DEV") else "sam"

setup(
    entry_points={
        "console_scripts": [f"{cmd_name}=samcli.cli.main:cli"],
    },
)
