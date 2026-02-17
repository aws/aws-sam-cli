"""Pipeline init options"""

from typing import Dict

from samcli.cli.row_modifiers import RowDefinition

PIPELINE_INIT_OPTION_NAMES = ["bootstrap"]
CONFIGURATION_OPTION_NAMES = ["config_env", "config_file", "save_params"]
BETA_OPTION_NAMES = ["beta_features"]
OTHER_OPTION_NAMES = ["help", "debug"]

ALL_OPTIONS = PIPELINE_INIT_OPTION_NAMES + CONFIGURATION_OPTION_NAMES + BETA_OPTION_NAMES + OTHER_OPTION_NAMES

OPTIONS_INFO: Dict[str, Dict] = {
    "Pipeline Init Options": {
        "option_names": {opt: {"rank": idx} for idx, opt in enumerate(PIPELINE_INIT_OPTION_NAMES)},
    },
    "Configuration Options": {
        "option_names": {opt: {"rank": idx} for idx, opt in enumerate(CONFIGURATION_OPTION_NAMES)},
        "extras": [
            RowDefinition(name="Learn more about configuration files at:"),
            RowDefinition(
                name="https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/"
                "serverless-sam-cli-config.html. "
            ),
        ],
    },
    "Beta Options": {
        "option_names": {opt: {"rank": idx} for idx, opt in enumerate(BETA_OPTION_NAMES)},
    },
    "Other Options": {
        "option_names": {opt: {"rank": idx} for idx, opt in enumerate(OTHER_OPTION_NAMES)},
    },
}
