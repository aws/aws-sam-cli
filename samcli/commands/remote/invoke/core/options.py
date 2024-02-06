"""
Remote Invoke Command Options related Datastructures for formatting.
"""

from typing import Dict, List

from samcli.cli.core.options import ALL_COMMON_OPTIONS, SAVE_PARAMS_OPTIONS, add_common_options_info
from samcli.cli.row_modifiers import RowDefinition

# NOTE: The ordering of the option lists matter, they are the order
# in which options will be displayed.

INFRASTRUCTURE_OPTION_NAMES: List[str] = ["stack_name"]

INPUT_EVENT_OPTIONS: List[str] = ["event", "event_file", "test_event_name"]

ADDITIONAL_OPTIONS: List[str] = ["parameter", "output"]

AWS_CREDENTIAL_OPTION_NAMES: List[str] = ["region", "profile"]

CONFIGURATION_OPTION_NAMES: List[str] = ["config_env", "config_file"] + SAVE_PARAMS_OPTIONS

OTHER_OPTIONS: List[str] = ["debug"]

ALL_OPTIONS: List[str] = (
    INFRASTRUCTURE_OPTION_NAMES
    + INPUT_EVENT_OPTIONS
    + ADDITIONAL_OPTIONS
    + AWS_CREDENTIAL_OPTION_NAMES
    + CONFIGURATION_OPTION_NAMES
    + ALL_COMMON_OPTIONS
)

OPTIONS_INFO: Dict[str, Dict] = {
    "Infrastructure Options": {
        "option_names": {opt: {"rank": idx} for idx, opt in enumerate(INFRASTRUCTURE_OPTION_NAMES)}
    },
    "Input Event Options": {"option_names": {opt: {"rank": idx} for idx, opt in enumerate(INPUT_EVENT_OPTIONS)}},
    "Additional Options": {"option_names": {opt: {"rank": idx} for idx, opt in enumerate(ADDITIONAL_OPTIONS)}},
    "AWS Credential Options": {
        "option_names": {opt: {"rank": idx} for idx, opt in enumerate(AWS_CREDENTIAL_OPTION_NAMES)}
    },
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
