"""
Terraform prepare hook implementation

This module contains the main prepare method
"""

import json
import logging
import os
from pathlib import Path
from subprocess import CalledProcessError, run
from typing import Any, Dict

from samcli.hook_packages.terraform.hooks.prepare.constants import CFN_CODE_PROPERTIES
from samcli.hook_packages.terraform.hooks.prepare.translate import translate_to_cfn
from samcli.lib.hook.exceptions import (
    PrepareHookException,
    TerraformCloudException,
    UnallowedEnvironmentVariableArgumentException,
)
from samcli.lib.utils import osutils
from samcli.lib.utils.subprocess_utils import LoadingPatternError, invoke_subprocess_with_loading_pattern

LOG = logging.getLogger(__name__)

TERRAFORM_METADATA_FILE = "template.json"
HOOK_METADATA_KEY = "AWS::SAM::Hook"
TERRAFORM_HOOK_METADATA = {
    "HookName": "terraform",
}

TF_CLOUD_LINK = (
    "https://docs.aws.amazon.com/serverless-application-model/latest"
    "/developerguide/gs-terraform-support.html#gs-terraform-support-cloud"
)
TF_CLOUD_EXCEPTION_MESSAGE = "Terraform Cloud does not support saving the generated execution plan"
TF_CLOUD_HELP_MESSAGE = (
    "Terraform Cloud does not currently support generating local plan "
    "files that AWS SAM CLI uses to parse the Terraform project.\n"
    "To use AWS SAM CLI with Terraform Cloud applications, provide "
    "a plan file using the --terraform-plan-file flag.\n\n"
    f"For more information, follow the link: {TF_CLOUD_LINK}"
)

TF_BLOCKED_ARGUMENTS = [
    "-target",
    "-destroy",
]
TF_ENVIRONMENT_VARIABLE_DELIM = "="
TF_ENVIRONMENT_VARIABLES = [
    "TF_CLI_ARGS",
    "TF_CLI_ARGS_plan",
    "TF_CLI_ARGS_apply",
]


def prepare(params: dict) -> dict:
    """
    Prepares a terraform application for use with the SAM CLI

    Parameters
    ----------
    params: dict
        Parameters of the IaC application

    Returns
    -------
    dict
        information of the generated metadata files
    """
    output_dir_path = params.get("OutputDirPath")

    terraform_application_dir = params.get("IACProjectPath", os.getcwd())
    project_root_dir = params.get("ProjectRootDir", terraform_application_dir)

    if not output_dir_path:
        raise PrepareHookException("OutputDirPath was not supplied")

    _validate_environment_variables()

    LOG.debug("Normalize the terraform application root module directory path %s", terraform_application_dir)
    if not os.path.isabs(terraform_application_dir):
        terraform_application_dir = os.path.normpath(os.path.join(os.getcwd(), terraform_application_dir))
        LOG.debug("The normalized terraform application root module directory path %s", terraform_application_dir)

    LOG.debug("Normalize the project root directory path %s", project_root_dir)
    if not os.path.isabs(project_root_dir):
        project_root_dir = os.path.normpath(os.path.join(os.getcwd(), project_root_dir))
        LOG.debug("The normalized project root directory path %s", project_root_dir)

    LOG.debug("Normalize the OutputDirPath %s", output_dir_path)
    if not os.path.isabs(output_dir_path):
        output_dir_path = os.path.normpath(os.path.join(terraform_application_dir, output_dir_path))
        LOG.debug("The normalized OutputDirPath value is %s", output_dir_path)

    skip_prepare_infra = params.get("SkipPrepareInfra", False)
    metadata_file_path = os.path.join(output_dir_path, TERRAFORM_METADATA_FILE)

    plan_file = params.get("PlanFile")

    if skip_prepare_infra and os.path.exists(metadata_file_path):
        LOG.info("Skipping preparation stage, the metadata file already exists at %s", metadata_file_path)
    else:
        try:
            # initialize terraform application
            if not plan_file:
                tf_json = _generate_plan_file(skip_prepare_infra, terraform_application_dir)
            else:
                LOG.info(f"Using provided plan file: {plan_file}")
                with open(plan_file, "r") as f:
                    tf_json = json.load(f)

            # convert terraform to cloudformation
            LOG.info("Generating metadata file")
            cfn_dict = translate_to_cfn(tf_json, output_dir_path, terraform_application_dir, project_root_dir)

            if cfn_dict.get("Resources"):
                _update_resources_paths(cfn_dict.get("Resources"), terraform_application_dir)  # type: ignore

            # Add hook metadata
            if not cfn_dict.get("Metadata"):
                cfn_dict["Metadata"] = {}
            cfn_dict["Metadata"][HOOK_METADATA_KEY] = TERRAFORM_HOOK_METADATA

            # store in supplied output dir
            if not os.path.exists(output_dir_path):
                os.makedirs(output_dir_path, exist_ok=True)

            LOG.info("Finished generating metadata file. Storing in %s", metadata_file_path)
            with open(metadata_file_path, "w+") as metadata_file:
                json.dump(cfn_dict, metadata_file)

        except OSError as e:
            raise PrepareHookException(f"OSError: {e}") from e

    return {"iac_applications": {"MainApplication": {"metadata_file": metadata_file_path}}}


def _update_resources_paths(cfn_resources: Dict[str, Any], terraform_application_dir: str) -> None:
    """
    As Sam Cli and terraform handles the relative paths differently. Sam Cli handles the relative paths to be relative
    to the template, but terraform handles them to be relative to the project root directory. This Function purpose is
    to update the CFN resources paths to be absolute paths, and change relative paths to be relative to the terraform
    application root directory.

    Parameters
    ----------
    cfn_resources: dict
        CloudFormation resources
    terraform_application_dir: str
        The terraform application root directory where all paths will be relative to it
    """
    resources_attributes_to_be_updated = {
        resource_type: [property_value] for resource_type, property_value in CFN_CODE_PROPERTIES.items()
    }
    for _, resource in cfn_resources.items():
        if resource.get("Type") in resources_attributes_to_be_updated and isinstance(resource.get("Properties"), dict):
            for attribute in resources_attributes_to_be_updated[resource["Type"]]:
                original_path = resource.get("Properties", {}).get(attribute)
                if isinstance(original_path, str) and not os.path.isabs(original_path):
                    resource["Properties"][attribute] = str(Path(terraform_application_dir).joinpath(original_path))


def _generate_plan_file(skip_prepare_infra: bool, terraform_application_dir: str) -> dict:
    """
    Call the relevant Terraform commands to generate, load and return the Terraform plan file
    which the AWS SAM CLI will then parse to extract the fields required to run local emulators.

    Parameters
    ----------
    skip_prepare_infra: bool
            Flag to skip skip prepare hook if we already have the metadata file. Default is False.
    terraform_application_dir: str
            The path where the hook can find the TF application.
    Returns
    -------
    dict
        The Terraform plan file in JSON format
    """
    log_msg = (
        (
            "The option to skip infrastructure preparation was provided, but AWS SAM CLI could not find "
            f"the metadata file. Preparing anyways.{os.linesep}Initializing Terraform application"
        )
        if skip_prepare_infra
        else "Initializing Terraform application"
    )
    LOG.info(log_msg)
    try:
        invoke_subprocess_with_loading_pattern(
            command_args={
                "args": ["terraform", "init", "-input=false"],
                "cwd": terraform_application_dir,
            },
            is_running_terraform_command=True,
        )

        # get json output of terraform plan
        LOG.info("Creating terraform plan and getting JSON output")
        with osutils.tempfile_platform_independent() as temp_file:
            invoke_subprocess_with_loading_pattern(
                # input false to avoid SAM CLI to stuck in case if the
                # Terraform project expects input, and customer does not provide it.
                command_args={
                    "args": ["terraform", "plan", "-out", temp_file.name, "-input=false"],
                    "cwd": terraform_application_dir,
                },
                is_running_terraform_command=True,
            )

            result = run(
                ["terraform", "show", "-json", temp_file.name],
                check=True,
                capture_output=True,
                cwd=terraform_application_dir,
            )
    except CalledProcessError as e:
        stderr_output = str(e.stderr)

        # stderr can take on bytes or just be a plain string depending on terminal
        if isinstance(e.stderr, bytes):
            stderr_output = e.stderr.decode("utf-8")

        # one of the subprocess.run calls resulted in non-zero exit code or some OS error
        LOG.debug(
            "Error running terraform command: \n" "cmd: %s \n" "stdout: %s \n" "stderr: %s \n",
            e.cmd,
            e.stdout,
            stderr_output,
        )

        raise PrepareHookException(
            f"There was an error while preparing the Terraform application.\n{stderr_output}"
        ) from e
    except LoadingPatternError as e:
        if TF_CLOUD_EXCEPTION_MESSAGE in e.message:
            raise TerraformCloudException(TF_CLOUD_HELP_MESSAGE)
        raise PrepareHookException(f"Error occurred when invoking a process:\n{e}") from e

    return dict(json.loads(result.stdout))


def _validate_environment_variables() -> None:
    """
    Validate that the Terraform environment variables do not contain blocked arguments.

    Raises
    ------
    UnallowedEnvironmentVariableArgumentException
        Raised when a Terraform related environment variable contains a blocked value
    """
    for env_var in TF_ENVIRONMENT_VARIABLES:
        env_value = os.environ.get(env_var, "")

        trimmed_arguments = []
        # get all trimmed arguments in a list and split on delim
        # eg.
        # "-foo=bar -hello" => ["-foo", "-hello"]
        for argument in env_value.split(" "):
            cleaned_argument = argument.strip()
            cleaned_argument = cleaned_argument.split(TF_ENVIRONMENT_VARIABLE_DELIM)[0]

            trimmed_arguments.append(cleaned_argument)

        if any([argument in TF_BLOCKED_ARGUMENTS for argument in trimmed_arguments]):
            message = (
                "Environment variable '%s' contains a blocked argument, please validate it does not contain: %s"
                % (
                    env_var,
                    TF_BLOCKED_ARGUMENTS,
                )
            )
            raise UnallowedEnvironmentVariableArgumentException(message)
