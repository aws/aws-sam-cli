"""
Delete Remote Test Event Command Options related Datastructures for formatting.
"""

from typing import Dict, List

from samcli.cli.core.options import ALL_COMMON_OPTIONS, add_common_options_info
from samcli.commands.remote.test_event.core.base_options import (
    AWS_CREDENTIAL_OPTION_INFO,
    AWS_CREDENTIAL_OPTION_NAMES,
    CONFIGURATION_OPTION_INFO,
    CONFIGURATION_OPTION_NAMES,
    INFRASTRUCTURE_OPTION_INFO,
    INFRASTRUCTURE_OPTION_NAMES,
    get_option_names,
)

# NOTE: The ordering of the option lists matter, they are the order
# in which options will be displayed.

EVENT_OPTIONS: List[str] = ["name"]

ALL_OPTIONS: List[str] = (
    INFRASTRUCTURE_OPTION_NAMES
    + EVENT_OPTIONS
    + AWS_CREDENTIAL_OPTION_NAMES
    + CONFIGURATION_OPTION_NAMES
    + ALL_COMMON_OPTIONS
)


OPTIONS_INFO: Dict[str, Dict] = {
    "Infrastructure Options": INFRASTRUCTURE_OPTION_INFO,
    "Test Event Options": {"option_names": get_option_names(EVENT_OPTIONS)},
    "AWS Credential Options": AWS_CREDENTIAL_OPTION_INFO,
    "Configuration Options": CONFIGURATION_OPTION_INFO,
}


add_common_options_info(OPTIONS_INFO)
