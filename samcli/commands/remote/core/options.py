"""
Shared Remote Command Options
"""

from typing import Dict, List

from samcli.cli.core.options import ALL_COMMON_OPTIONS, SAVE_PARAMS_OPTIONS, add_common_options_info

# NOTE: The ordering of the option lists matter, they are the order
# in which options will be displayed.

AWS_CREDENTIAL_OPTION_NAMES: List[str] = ["region", "profile"]

CONFIGURATION_OPTION_NAMES: List[str] = ["config_env", "config_file"] + SAVE_PARAMS_OPTIONS

ALL_OPTIONS: List[str] = AWS_CREDENTIAL_OPTION_NAMES + CONFIGURATION_OPTION_NAMES + ALL_COMMON_OPTIONS

OPTIONS_INFO: Dict[str, Dict] = {
    "AWS Credential Options": {
        "option_names": {opt: {"rank": idx} for idx, opt in enumerate(AWS_CREDENTIAL_OPTION_NAMES)}
    },
    "Configuration Options": {
        "option_names": {opt: {"rank": idx} for idx, opt in enumerate(CONFIGURATION_OPTION_NAMES)}
    },
}

add_common_options_info(OPTIONS_INFO)
