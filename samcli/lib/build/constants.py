"""
build constants
"""
from typing import Set

DEPRECATED_RUNTIMES: Set[str] = {
    "nodejs4.3",
    "nodejs6.10",
    "nodejs8.10",
    "nodejs10.x",
    "dotnetcore2.0",
    "dotnetcore2.1",
    "dotnetcore3.1",
    "python2.7",
    "python3.6",
    "ruby2.5",
}
BUILD_PROPERTIES = "BuildProperties"
