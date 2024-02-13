"""
Init Command Options related Datastructures for formatting.
"""

from typing import Dict, List

from samcli.cli.core.options import ALL_COMMON_OPTIONS, SAVE_PARAMS_OPTIONS, add_common_options_info
from samcli.cli.row_modifiers import RowDefinition

# The ordering of the option lists matter, they are the order in which options will be displayed.

APPLICATION_OPTIONS: List[str] = [
    "name",
    "architecture",
    "runtime",
    "dependency_manager",
    "location",
    "package_type",
    "base_image",
    "app_template",
    "output_dir",
]

# Can be used instead of the options in the first list
NON_INTERACTIVE_OPTIONS: List[str] = ["no_interactive", "no_input", "extra_context"]

CONFIGURATION_OPTION_NAMES: List[str] = ["config_env", "config_file"] + SAVE_PARAMS_OPTIONS

ADDITIONAL_OPTIONS: List[str] = ["tracing", "application_insights", "structured_logging"]

ALL_OPTIONS: List[str] = (
    APPLICATION_OPTIONS + NON_INTERACTIVE_OPTIONS + CONFIGURATION_OPTION_NAMES + ADDITIONAL_OPTIONS + ALL_COMMON_OPTIONS
)

OPTIONS_INFO: Dict[str, Dict] = {
    "Application Options": {
        "option_names": {opt: {"rank": idx} for idx, opt in enumerate(APPLICATION_OPTIONS)},
        "extras": [RowDefinition(name="")],
    },
    "Non Interactive Options": {
        "option_names": {opt: {"rank": idx} for idx, opt in enumerate(NON_INTERACTIVE_OPTIONS)}
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
