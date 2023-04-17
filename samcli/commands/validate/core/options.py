"""
Validate Command Options related Datastructures for formatting.
"""
from typing import Dict, List

from samcli.cli.row_modifiers import RowDefinition

# NOTE(sriram-mv): The ordering of the option lists matter, they are the order
# in which options will be displayed.

REQUIRED_OPTIONS: List[str] = ["template_file"]

AWS_CREDENTIAL_OPTION_NAMES: List[str] = ["region", "profile"]

LINT_OPTION_NAMES: List[str] = [
    "lint",
]

CONFIGURATION_OPTION_NAMES: List[str] = ["config_env", "config_file"]

OTHER_OPTIONS: List[str] = ["debug"]

ALL_OPTIONS: List[str] = (
    REQUIRED_OPTIONS + LINT_OPTION_NAMES + AWS_CREDENTIAL_OPTION_NAMES + CONFIGURATION_OPTION_NAMES + OTHER_OPTIONS
)

OPTIONS_INFO: Dict[str, Dict] = {
    "Required Options": {"option_names": {opt: {"rank": idx} for idx, opt in enumerate(REQUIRED_OPTIONS)}},
    "Lint Options": {"option_names": {opt: {"rank": idx} for idx, opt in enumerate(LINT_OPTION_NAMES)}},
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
    "Other Options": {"option_names": {opt: {"rank": idx} for idx, opt in enumerate(OTHER_OPTIONS)}},
}
