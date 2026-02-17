"""
Delete Command Options
"""

from typing import Dict

from samcli.cli.core.options import ALL_COMMON_OPTIONS, add_common_options_info
from samcli.cli.row_modifiers import RowDefinition

DELETE_OPTION_NAMES = ["stack_name", "no_prompts", "s3_bucket", "s3_prefix"]
AWS_CREDENTIAL_OPTION_NAMES = ["region", "profile"]
CONFIGURATION_OPTION_NAMES = ["config_file", "config_env", "save_params"]

ALL_OPTIONS = DELETE_OPTION_NAMES + AWS_CREDENTIAL_OPTION_NAMES + CONFIGURATION_OPTION_NAMES + ALL_COMMON_OPTIONS

OPTIONS_INFO: Dict[str, Dict] = {
    "Delete Options": {"option_names": {opt: {"rank": idx} for idx, opt in enumerate(DELETE_OPTION_NAMES)}},
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
