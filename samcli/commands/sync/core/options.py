"""
Sync Command Options related Datastructures for formatting.
"""
from typing import Dict

from samcli.cli.row_modifiers import RowDefinition

REQUIRED_OPTIONS = ["stack_name", "template_file"]

AWS_CREDENTIAL_OPTION_NAMES = ["region", "profile"]

INFRASTRUCTURE_OPTION_NAMES = [
    "parameter_overrides",
    "capabilities",
    "s3_bucket",
    "s3_prefix",
    "image_repository",
    "image_repositories",
    "kms_key_id",
    "role_arn",
    "notification_arns",
    "tags",
    "metadata",
]

CONFIGURATION_OPTION_NAMES = ["config_env", "config_file"]

ADDITIONAL_OPTIONS = [
    "dependency_layer",
    "watch",
    "code",
    "resource_id",
    "resource",
    "use_container",
    "base_dir",
]
OTHER_OPTIONS = ["debug", "help"]

ALL_OPTIONS = (
    REQUIRED_OPTIONS
    + AWS_CREDENTIAL_OPTION_NAMES
    + INFRASTRUCTURE_OPTION_NAMES
    + CONFIGURATION_OPTION_NAMES
    + ADDITIONAL_OPTIONS
    + OTHER_OPTIONS
)

OPTIONS_INFO: Dict[str, Dict] = {
    "Required Options": {
        "option_names": REQUIRED_OPTIONS,
    },
    "AWS Credential Options": {
        "option_names": AWS_CREDENTIAL_OPTION_NAMES,
    },
    "Infrastructure Options": {
        "option_names": INFRASTRUCTURE_OPTION_NAMES,
    },
    "Configuration Options": {
        "option_names": CONFIGURATION_OPTION_NAMES,
        "extras": [
            RowDefinition(name="Learn more about configuration files at:"),
            RowDefinition(
                name="https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli"
                "-config.html. "
            ),
        ],
    },
    "Additional Options": {
        "option_names": ADDITIONAL_OPTIONS,
    },
    "Other Options": {
        "option_names": OTHER_OPTIONS,
    },
}
