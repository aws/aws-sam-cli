"""
Deploy Command Options related Datastructures for formatting.
"""

from typing import Dict, List

from samcli.cli.core.options import ALL_COMMON_OPTIONS, SAVE_PARAMS_OPTIONS, add_common_options_info
from samcli.cli.row_modifiers import RowDefinition

# The ordering of the option lists matter, they are the order in which options will be displayed.

REQUIRED_OPTIONS: List[str] = ["stack_name", "capabilities", "resolve_s3"]

# Can be used instead of the options in the first list
INTERACTIVE_OPTIONS: List[str] = ["guided"]

AWS_CREDENTIAL_OPTION_NAMES: List[str] = ["region", "profile"]

INFRASTRUCTURE_OPTION_NAMES: List[str] = [
    "parameter_overrides",
    "s3_bucket",
    "s3_prefix",
    "resolve_image_repos",
    "image_repository",
    "image_repositories",
    "role_arn",
    "kms_key_id",
    "notification_arns",
    "tags",
    "metadata",
]

DEPLOYMENT_OPTIONS: List[str] = [
    "no_execute_changeset",
    "fail_on_empty_changeset",
    "confirm_changeset",
    "disable_rollback",
    "on_failure",
    "force_upload",
    "max_wait_duration",
]

CONFIGURATION_OPTION_NAMES: List[str] = ["config_env", "config_file"] + SAVE_PARAMS_OPTIONS

ADDITIONAL_OPTIONS: List[str] = [
    "no_progressbar",
    "signing_profiles",
    "template_file",
    "use_json",
]

ALL_OPTIONS: List[str] = (
    REQUIRED_OPTIONS
    + INTERACTIVE_OPTIONS
    + AWS_CREDENTIAL_OPTION_NAMES
    + INFRASTRUCTURE_OPTION_NAMES
    + DEPLOYMENT_OPTIONS
    + CONFIGURATION_OPTION_NAMES
    + ADDITIONAL_OPTIONS
    + ALL_COMMON_OPTIONS
)

OPTIONS_INFO: Dict[str, Dict] = {
    "Required Options": {"option_names": {opt: {"rank": idx} for idx, opt in enumerate(REQUIRED_OPTIONS)}},
    "Interactive Options": {
        "option_names": {opt: {"rank": idx} for idx, opt in enumerate(INTERACTIVE_OPTIONS)},
        "extras": [
            RowDefinition(name="Use the guided flag for a step-by-step flow instead of using the required options. ")
        ],
    },
    "AWS Credential Options": {
        "option_names": {opt: {"rank": idx} for idx, opt in enumerate(AWS_CREDENTIAL_OPTION_NAMES)}
    },
    "Infrastructure Options": {
        "option_names": {opt: {"rank": idx} for idx, opt in enumerate(INFRASTRUCTURE_OPTION_NAMES)}
    },
    "Deployment Options": {"option_names": {opt: {"rank": idx} for idx, opt in enumerate(DEPLOYMENT_OPTIONS)}},
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
