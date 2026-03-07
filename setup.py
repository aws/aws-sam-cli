#!/usr/bin/env python

import os
from setuptools import setup

# When SAM_CLI_DEV is set, register "samdev" as the console script instead of "sam".
# The default "sam" entry point is declared in pyproject.toml [project.scripts].
# All other metadata (name, version, dependencies, etc.) is defined in pyproject.toml.
cmd_name = "sam"
if os.getenv("SAM_CLI_DEV"):
    cmd_name = "samdev"

setup_kwargs = {}
if os.getenv("SAM_CLI_DEV"):
    setup_kwargs["entry_points"] = {
        "console_scripts": [f"{cmd_name}=samcli.cli.main:cli"],
    }

setup(**setup_kwargs)
