"""
Package Command Options related Datastructures for formatting.
"""

from typing import Dict, List

from samcli.cli.core.options import ALL_COMMON_OPTIONS, SAVE_PARAMS_OPTIONS, add_common_options_info
from samcli.cli.row_modifiers import RowDefinition

# The ordering of the option lists matter, they are the order in which options will be displayed.

REQUIRED_OPTIONS: List[str] = ["s3_bucket", "resolve_s3"]

AWS_CREDENTIAL_OPTION_NAMES: List[str] = ["region", "profile"]

INFRASTRUCTURE_OPTION_NAMES: List[str] = [
    "s3_prefix",
    "image_repository",
    "image_repositories",
    "kms_key_id",
    "metadata",
]

DEPLOYMENT_OPTIONS: List[str] = [
    "force_upload",
]

CONFIGURATION_OPTION_NAMES: List[str] = ["config_env", "config_file"] + SAVE_PARAMS_OPTIONS

ADDITIONAL_OPTIONS: List[str] = [
    "no_progressbar",
    "signing_profiles",
    "template_file",
    "output_template_file",
    "use_json",
]

ALL_OPTIONS: List[str] = (
    REQUIRED_OPTIONS
    + AWS_CREDENTIAL_OPTION_NAMES
    + INFRASTRUCTURE_OPTION_NAMES
    + DEPLOYMENT_OPTIONS
    + CONFIGURATION_OPTION_NAMES
    + ADDITIONAL_OPTIONS
    + ALL_COMMON_OPTIONS
)

OPTIONS_INFO: Dict[str, Dict] = {
    "Required Options": {"option_names": {opt: {"rank": idx} for idx, opt in enumerate(REQUIRED_OPTIONS)}},
    "AWS Credential Options": {
        "option_names": {opt: {"rank": idx} for idx, opt in enumerate(AWS_CREDENTIAL_OPTION_NAMES)}
    },
    "Infrastructure Options": {
        "option_names": {opt: {"rank": idx} for idx, opt in enumerate(INFRASTRUCTURE_OPTION_NAMES)}
    },
    "Package Management Options": {"option_names": {opt: {"rank": idx} for idx, opt in enumerate(DEPLOYMENT_OPTIONS)}},
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
    "Additional Options": {"option_names": {opt: {"rank": idx} for idx, opt in enumerate(ADDITIONAL_OPTIONS)}},
}
add_common_options_info(OPTIONS_INFO)
