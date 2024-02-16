"""
Remote Test Event Command Options related Datastructures for formatting.
"""

from typing import Dict, List

from samcli.cli.row_modifiers import RowDefinition

# NOTE: The ordering of the option lists matter, they are the order
# in which options will be displayed.

INFRASTRUCTURE_OPTION_NAMES: List[str] = ["stack_name"]

AWS_CREDENTIAL_OPTION_NAMES: List[str] = ["region", "profile"]

CONFIGURATION_OPTION_NAMES: List[str] = ["config_env", "config_file"]


def get_option_names(option_names: List[str]) -> Dict[str, Dict]:
    return {opt: {"rank": idx} for idx, opt in enumerate(option_names)}


CONFIGURATION_OPTION_INFO = {
    "option_names": get_option_names(CONFIGURATION_OPTION_NAMES),
    "extras": [
        RowDefinition(name="Learn more about configuration files at:"),
        RowDefinition(
            name="https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli"
            "-config.html. "
        ),
    ],
}

INFRASTRUCTURE_OPTION_INFO = {"option_names": get_option_names(INFRASTRUCTURE_OPTION_NAMES)}

AWS_CREDENTIAL_OPTION_INFO = {"option_names": get_option_names(AWS_CREDENTIAL_OPTION_NAMES)}
