"""
build constants
"""

from typing import Set

DEPRECATED_RUNTIMES: Set[str] = {
    "nodejs4.3",
    "nodejs6.10",
    "nodejs8.10",
    "nodejs10.x",
    "nodejs12.x",
    "nodejs14.x",
    "dotnetcore2.0",
    "dotnetcore2.1",
    "dotnetcore3.1",
    "java8",
    "python2.7",
    "python3.6",
    "python3.7",
    "ruby2.5",
    "ruby2.7",
}
BUILD_PROPERTIES = "BuildProperties"
