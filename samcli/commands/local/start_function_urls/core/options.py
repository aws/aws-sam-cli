"""
Start Function URLs Command Options related Datastructures for formatting.
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

FUNCTION_URL_OPTIONS: List[str] = [
    "host",
    "port_range",
    "function_name",
    "port",
    "disable_authorizer",
]

CONTAINER_OPTION_NAMES: List[str] = [
    "env_vars",
    "container_env_vars",
    "debug_port",
    "debugger_path",
    "debug_args",
    "debug_function",
    "docker_volume_basedir",
    "skip_pull_image",
    "docker_network",
    "force_image_build",
    "no_memory_limit",
    "warm_containers",
    "shutdown",
    "container_host",
    "container_host_interface",
    "add_host",
    "invoke_image",
]

CONFIGURATION_OPTION_NAMES: List[str] = ["config_env", "config_file"] + SAVE_PARAMS_OPTIONS

ARTIFACT_LOCATION_OPTIONS: List[str] = [
    "log_file",
    "layer_cache_basedir",
]

ALL_OPTIONS: List[str] = (
    REQUIRED_OPTIONS
    + TEMPLATE_OPTIONS
    + FUNCTION_URL_OPTIONS
    + AWS_CREDENTIAL_OPTION_NAMES
    + CONTAINER_OPTION_NAMES
    + ARTIFACT_LOCATION_OPTIONS
    + CONFIGURATION_OPTION_NAMES
    + ALL_COMMON_OPTIONS
)

OPTIONS_INFO: Dict[str, Dict] = {
    "Required Options": {"option_names": {opt: {"rank": idx} for idx, opt in enumerate(REQUIRED_OPTIONS)}},
    "Template Options": {"option_names": {opt: {"rank": idx} for idx, opt in enumerate(TEMPLATE_OPTIONS)}},
    "Function URL Options": {
        "option_names": {opt: {"rank": idx} for idx, opt in enumerate(FUNCTION_URL_OPTIONS)},
        "extras": [
            RowDefinition(name="Each function with FunctionUrlConfig gets its own port."),
            RowDefinition(name="Use port-range to specify available ports for auto-assignment."),
        ],
    },
    "AWS Credential Options": {
        "option_names": {opt: {"rank": idx} for idx, opt in enumerate(AWS_CREDENTIAL_OPTION_NAMES)}
    },
    "Container Options": {"option_names": {opt: {"rank": idx} for idx, opt in enumerate(CONTAINER_OPTION_NAMES)}},
    "Artifact Location Options": {
        "option_names": {opt: {"rank": idx} for idx, opt in enumerate(ARTIFACT_LOCATION_OPTIONS)}
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
