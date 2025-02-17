"""
Invoke Start Lambda Command Options related Datastructures for formatting.
"""

from typing import Dict, List

from samcli.cli.core.options import ALL_COMMON_OPTIONS, SAVE_PARAMS_OPTIONS, add_common_options_info
from samcli.cli.row_modifiers import RowDefinition

# NOTE(sriram-mv): The ordering of the option lists matter, they are the order
# in which options will be displayed.

REQUIRED_OPTIONS: List[str] = ["template_file"]

AWS_CREDENTIAL_OPTION_NAMES: List[str] = ["region", "profile"]

TEMPLATE_OPTIONS: List[str] = [
    "parameter_overrides",
]

CONTAINER_OPTION_NAMES: List[str] = [
    "host",
    "port",
    "env_vars",
    "warm_containers",
    "container_env_vars",
    "debug_function",
    "debug_port",
    "debugger_path",
    "debug_args",
    "docker_volume_basedir",
    "skip_pull_image",
    "docker_network",
    "force_image_build",
    "shutdown",
    "container_host",
    "container_host_interface",
    "add_host",
    "invoke_image",
    "no_memory_limit",
]

ARTIFACT_LOCATION_OPTIONS: List[str] = [
    "log_file",
    "layer_cache_basedir",
]

EXTENSION_OPTIONS: List[str] = ["hook_name", "skip_prepare_infra"]

CONFIGURATION_OPTION_NAMES: List[str] = ["config_env", "config_file"] + SAVE_PARAMS_OPTIONS

TERRAFORM_HOOK_OPTIONS: List[str] = ["terraform_plan_file"]

ALL_OPTIONS: List[str] = (
    REQUIRED_OPTIONS
    + TEMPLATE_OPTIONS
    + AWS_CREDENTIAL_OPTION_NAMES
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
