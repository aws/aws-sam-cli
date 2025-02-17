"""
Build Command Options related Datastructures for formatting.
"""

from typing import Dict, List

from samcli.cli.core.options import ALL_COMMON_OPTIONS, SAVE_PARAMS_OPTIONS, add_common_options_info
from samcli.cli.row_modifiers import RowDefinition

# NOTE(sriram-mv): The ordering of the option lists matter, they are the order
# in which options will be displayed.

REQUIRED_OPTIONS: List[str] = ["template_file"]

AWS_CREDENTIAL_OPTION_NAMES: List[str] = ["region", "profile"]

CONTAINER_OPTION_NAMES: List[str] = [
    "use_container",
    "container_env_var",
    "container_env_var_file",
    "build_image",
    "mount_with",
    "skip_pull_image",
    "docker_network",
    "mount_symlinks",
]

CONFIGURATION_OPTION_NAMES: List[str] = ["config_env", "config_file"] + SAVE_PARAMS_OPTIONS

EXTENSION_OPTIONS: List[str] = ["hook_name", "skip_prepare_infra"]

BUILD_STRATEGY_OPTIONS: List[str] = ["parallel", "exclude", "manifest", "cached", "build_in_source"]

ARTIFACT_LOCATION_OPTIONS: List[str] = [
    "build_dir",
    "cache_dir",
    "base_dir",
]

TEMPLATE_OPTIONS: List[str] = ["parameter_overrides"]

TERRAFORM_HOOK_OPTIONS: List[str] = ["terraform_project_root_path"]

ALL_OPTIONS: List[str] = (
    REQUIRED_OPTIONS
    + TEMPLATE_OPTIONS
    + AWS_CREDENTIAL_OPTION_NAMES
    + BUILD_STRATEGY_OPTIONS
    + CONTAINER_OPTION_NAMES
    + ARTIFACT_LOCATION_OPTIONS
    + EXTENSION_OPTIONS
    + CONFIGURATION_OPTION_NAMES
    + ALL_COMMON_OPTIONS
    + TERRAFORM_HOOK_OPTIONS
)

OPTIONS_INFO: Dict[str, Dict] = {
    "Required Options": {"option_names": {opt: {"rank": idx} for idx, opt in enumerate(REQUIRED_OPTIONS)}},
    "Template Options": {"option_names": {opt: {"rank": idx} for idx, opt in enumerate(TEMPLATE_OPTIONS)}},
    "AWS Credential Options": {
        "option_names": {opt: {"rank": idx} for idx, opt in enumerate(AWS_CREDENTIAL_OPTION_NAMES)}
    },
    "Build Strategy Options": {"option_names": {opt: {"rank": idx} for idx, opt in enumerate(BUILD_STRATEGY_OPTIONS)}},
    "Container Options": {"option_names": {opt: {"rank": idx} for idx, opt in enumerate(CONTAINER_OPTION_NAMES)}},
    "Artifact Location Options": {
        "option_names": {opt: {"rank": idx} for idx, opt in enumerate(ARTIFACT_LOCATION_OPTIONS)}
    },
    "Extension Options": {"option_names": {opt: {"rank": idx} for idx, opt in enumerate(EXTENSION_OPTIONS)}},
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
    "Terraform Hook Options": {"option_names": {opt: {"rank": idx} for idx, opt in enumerate(TERRAFORM_HOOK_OPTIONS)}},
}
add_common_options_info(OPTIONS_INFO)
