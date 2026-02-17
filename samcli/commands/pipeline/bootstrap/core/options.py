"""Pipeline bootstrap options"""

from typing import Dict

from samcli.cli.row_modifiers import RowDefinition

BOOTSTRAP_OPTION_NAMES = [
    "interactive",
    "stage",
    "pipeline_user",
    "pipeline_execution_role",
    "cloudformation_execution_role",
    "bucket",
    "create_image_repository",
    "image_repository",
    "confirm_changeset",
    "permissions_provider",
    "oidc_provider_url",
    "oidc_client_id",
    "github_org",
    "github_repo",
    "deployment_branch",
    "oidc_provider",
    "gitlab_group",
    "gitlab_project",
    "bitbucket_repo_uuid",
    "cicd_provider",
]
AWS_CREDENTIAL_OPTION_NAMES = ["region", "profile"]
CONFIGURATION_OPTION_NAMES = ["config_env", "config_file", "save_params"]
BETA_OPTION_NAMES = ["beta_features"]
OTHER_OPTION_NAMES = ["help", "debug"]

ALL_OPTIONS = (
    BOOTSTRAP_OPTION_NAMES
    + AWS_CREDENTIAL_OPTION_NAMES
    + CONFIGURATION_OPTION_NAMES
    + BETA_OPTION_NAMES
    + OTHER_OPTION_NAMES
)

OPTIONS_INFO: Dict[str, Dict] = {
    "Bootstrap Options": {
        "option_names": {opt: {"rank": idx} for idx, opt in enumerate(BOOTSTRAP_OPTION_NAMES)},
    },
    "AWS Credential Options": {
        "option_names": {opt: {"rank": idx} for idx, opt in enumerate(AWS_CREDENTIAL_OPTION_NAMES)},
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
