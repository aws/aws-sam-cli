"""
build constants
"""

from typing import Set

from samcli.lib.runtimes.base import DeprecatedRuntime

DEPRECATED_RUNTIMES: Set[str] = set([r.key for r in DeprecatedRuntime])
BUILD_PROPERTIES = "BuildProperties"
