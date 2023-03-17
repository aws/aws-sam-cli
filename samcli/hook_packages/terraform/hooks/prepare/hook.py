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
from samcli.lib.hook.exceptions import PrepareHookException
from samcli.lib.utils import osutils
from samcli.lib.utils.subprocess_utils import LoadingPatternError, invoke_subprocess_with_loading_pattern

LOG = logging.getLogger(__name__)

TERRAFORM_METADATA_FILE = "template.json"
HOOK_METADATA_KEY = "AWS::SAM::Hook"
TERRAFORM_HOOK_METADATA = {
    "HookName": "terraform",
}


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
    if not output_dir_path:
        raise PrepareHookException("OutputDirPath was not supplied")

    LOG.debug("Normalize the project root directory path %s", terraform_application_dir)
    if not os.path.isabs(terraform_application_dir):
        terraform_application_dir = os.path.normpath(os.path.join(os.getcwd(), terraform_application_dir))
        LOG.debug("The normalized project root directory path %s", terraform_application_dir)

    LOG.debug("Normalize the OutputDirPath %s", output_dir_path)
    if not os.path.isabs(output_dir_path):
        output_dir_path = os.path.normpath(os.path.join(terraform_application_dir, output_dir_path))
        LOG.debug("The normalized OutputDirPath value is %s", output_dir_path)

    skip_prepare_infra = params.get("SkipPrepareInfra")
    metadata_file_path = os.path.join(output_dir_path, TERRAFORM_METADATA_FILE)

    if skip_prepare_infra and os.path.exists(metadata_file_path):
        LOG.info("Skipping preparation stage, the metadata file already exists at %s", metadata_file_path)
    else:
        log_msg = (
            (
                "The option to skip infrastructure preparation was provided, but AWS SAM CLI could not find "
                f"the metadata file. Preparing anyways.{os.linesep}Initializing Terraform application"
            )
            if skip_prepare_infra
            else "Initializing Terraform application"
        )
        try:
            # initialize terraform application
            LOG.info(log_msg)
            invoke_subprocess_with_loading_pattern(
                command_args={
                    "args": ["terraform", "init", "-input=false"],
                    "cwd": terraform_application_dir,
                }
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
                    }
                )

                result = run(
                    ["terraform", "show", "-json", temp_file.name],
                    check=True,
                    capture_output=True,
                    cwd=terraform_application_dir,
                )
            tf_json = json.loads(result.stdout)

            # convert terraform to cloudformation
            LOG.info("Generating metadata file")
            cfn_dict = translate_to_cfn(tf_json, output_dir_path, terraform_application_dir)

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
            raise PrepareHookException(f"Error occurred when invoking a process: {e}") from e
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
