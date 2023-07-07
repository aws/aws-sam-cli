"""
Sync Command Options related Datastructures for formatting.
"""
from typing import Dict, List

from samcli.cli.core.options import ALL_COMMON_OPTIONS, add_common_options_info
from samcli.cli.row_modifiers import RowDefinition

# NOTE(sriram-mv): The ordering of the option lists matter, they are the order
# in which options will be displayed.

REQUIRED_OPTIONS: List[str] = ["stack_name", "template_file"]

AWS_CREDENTIAL_OPTION_NAMES: List[str] = ["region", "profile"]

INFRASTRUCTURE_OPTION_NAMES: List[str] = [
    "parameter_overrides",
    "capabilities",
    "s3_bucket",
    "s3_prefix",
    "image_repository",
    "image_repositories",
    "role_arn",
    "kms_key_id",
    "notification_arns",
    "tags",
    "metadata",
    "build_image",
]

CONFIGURATION_OPTION_NAMES: List[str] = ["config_env", "config_file"]

ADDITIONAL_OPTIONS: List[str] = [
    "watch",
    "code",
    "skip_deploy_sync",
    "dependency_layer",
    "use_container",
    "resource_id",
    "resource",
    "base_dir",
]
OTHER_OPTIONS: List[str] = ["debug", "help"]

ALL_OPTIONS: List[str] = (
    REQUIRED_OPTIONS
    + AWS_CREDENTIAL_OPTION_NAMES
    + INFRASTRUCTURE_OPTION_NAMES
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
