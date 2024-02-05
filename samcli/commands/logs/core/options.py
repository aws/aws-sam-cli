"""
Logs Command Options related Datastructures for formatting.
"""

from typing import Dict, List

from samcli.cli.core.options import ALL_COMMON_OPTIONS, SAVE_PARAMS_OPTIONS, add_common_options_info
from samcli.cli.row_modifiers import RowDefinition

# The ordering of the option lists matter, they are the order in which options will be displayed.

LOG_IDENTIFIER_OPTIONS: List[str] = ["stack_name", "cw_log_group", "name"]

# Can be used instead of the options in the first list
ADDITIONAL_OPTIONS: List[str] = ["include_traces", "filter", "output", "tail", "start_time", "end_time"]

AWS_CREDENTIAL_OPTION_NAMES: List[str] = ["region", "profile"]

CONFIGURATION_OPTION_NAMES: List[str] = ["config_env", "config_file"] + SAVE_PARAMS_OPTIONS

ALL_OPTIONS: List[str] = (
    LOG_IDENTIFIER_OPTIONS
    + AWS_CREDENTIAL_OPTION_NAMES
    + ADDITIONAL_OPTIONS
    + CONFIGURATION_OPTION_NAMES
    + ALL_COMMON_OPTIONS
)

OPTIONS_INFO: Dict[str, Dict] = {
    "Log Identifier Options": {"option_names": {opt: {"rank": idx} for idx, opt in enumerate(LOG_IDENTIFIER_OPTIONS)}},
    "AWS Credential Options": {
        "option_names": {opt: {"rank": idx} for idx, opt in enumerate(AWS_CREDENTIAL_OPTION_NAMES)}
    },
    "Additional Options": {"option_names": {opt: {"rank": idx} for idx, opt in enumerate(ADDITIONAL_OPTIONS)}},
    "Configuration Options": {
        "option_names": {opt: {"rank": idx} for idx, opt in enumerate(CONFIGURATION_OPTION_NAMES)},
        "extras": [
            RowDefinition(name="Learn more about configuration files at:"),
            RowDefinition(
                name="https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli"
                "-config.html. "
            ),
        ],
    },
}
add_common_options_info(OPTIONS_INFO)
