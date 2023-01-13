"""
click callback to validate importing a list of modules from a txt file
This is used to validate a freshly installed SAM CLI has all the hidden imports  
"""
import logging
from pathlib import Path

from pkg_resources import get_distribution, DistributionNotFound


LOG = logging.getLogger(__name__)


def validate_samcli(samcli_modules_file: Path) -> bool:
    """
    Validate if all samcli sub-modules can be imported
    """
    with open(samcli_modules_file, "r") as f:
        modules = [l.strip() for l in f.readlines()]

    if not modules:
        LOG.info("module list is empty")
        return False

    for module_name in modules:
        try:
            __import__(module_name.strip())
        except ImportError:
            LOG.info("ImportError: %s", module_name)
            return False

    return True


def validate_requirements(requirements_file: Path) -> bool:
    """
    Validates if
    """
    with open(requirements_file, "r", encoding="utf-8") as f:
        lines = []
        newline = ""
        for line in f:
            line = line.strip()
            if line.startswith("#"):
                continue
            line_ended = not line.endswith("\\")
            newline += line if line_ended else line[:-1]
            if line_ended:
                lines.append(newline)
                newline = ""
    packages = [l.split("==")[0] for l in lines]
    for package in packages:
        try:
            get_distribution(package)
        except DistributionNotFound:
            LOG.info("Cannot find distribution: %s", package)
            return False
    return True
