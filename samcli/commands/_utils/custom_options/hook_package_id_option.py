"""
Custom Click options for hook package id
"""

import logging
import os
import click

from samcli.commands._utils.constants import DEFAULT_BUILT_TEMPLATE_PATH
from samcli.commands._utils.experimental import (
    prompt_experimental,
    ExperimentalFlag,
    set_experimental,
    update_experimental_context,
)
from samcli.lib.hook.exceptions import InvalidHookWrapperException
from samcli.lib.hook.hook_wrapper import IacHookWrapper, get_available_hook_packages_ids

LOG = logging.getLogger(__name__)


class HookPackageIdOption(click.Option):
    """
    A custom option class that allows do custom validation for the SAM CLI commands options in case if hook package
    id is passed. It also calls the correct IaC prepare hook, and update the SAM CLI commands options based on the
    prepare hook output.
    """

    def __init__(self, *args, **kwargs):
        self._force_prepare = kwargs.pop("force_prepare", True)
        self._invalid_coexist_options = kwargs.pop("invalid_coexist_options", [])
        super().__init__(*args, **kwargs)

    def handle_parse_result(self, ctx, opts, args):
        opt_name = self.name.replace("_", "-")
        if self.name not in opts:
            return super().handle_parse_result(ctx, opts, args)
        command_name = ctx.command.name
        if command_name in ["invoke", "start-lambda", "start-api"]:
            command_name = f"local {command_name}"
        # validate the hook_package_id value exists
        hook_package_id = opts[self.name]
        iac_hook_wrapper = None
        try:
            iac_hook_wrapper = IacHookWrapper(hook_package_id)
        except InvalidHookWrapperException as e:
            raise click.BadParameter(
                f"{hook_package_id} is not a valid hook package id."
                f"{os.linesep}valid package ids: {get_available_hook_packages_ids()}"
            ) from e

        self._validate_coexist_options(opt_name, opts)

        _validate_build_command_parameters(command_name, opts)

        if not _check_experimental_flag(hook_package_id, command_name, opts):
            return super().handle_parse_result(ctx, opts, args)

        self._call_prepare_hook(iac_hook_wrapper, opts)
        return super().handle_parse_result(ctx, opts, args)

    def _call_prepare_hook(self, iac_hook_wrapper, opts):
        # call prepare hook
        built_template_path = DEFAULT_BUILT_TEMPLATE_PATH
        if not self._force_prepare and os.path.exists(built_template_path):
            LOG.info("Skipped prepare hook. Current application is already prepared.")
        else:
            LOG.info("Running Prepare Hook to prepare the current application")

            iac_project_path = os.getcwd()
            output_dir_path = os.path.join(iac_project_path, ".aws-sam-iacs", "iacs_metadata")
            if not os.path.exists(output_dir_path):
                os.makedirs(output_dir_path, exist_ok=True)
            debug = opts.get("debug", False)
            aws_profile = opts.get("profile")
            aws_region = opts.get("region")
            metadata_file = iac_hook_wrapper.prepare(output_dir_path, iac_project_path, debug, aws_profile, aws_region)

            LOG.info("Prepare hook completed and metadata file generated at: %s", metadata_file)
            opts["template_file"] = metadata_file

    def _validate_coexist_options(self, opt_name, opts):
        # validate coexist options
        for invalid_opt in self._invalid_coexist_options:
            invalid_opt_name = invalid_opt.replace("-", "_")
            if invalid_opt_name in opts:
                raise click.BadParameter(
                    f"Parameters {opt_name}, and {','.join(self._invalid_coexist_options)} cannot be used together"
                )


def _validate_build_command_parameters(command_name, opts):
    # validate build-image is provided in case of build using container
    # add this validation here to avoid running hook prepare and there is issue
    if command_name == "build" and opts.get("use_container") and not opts.get("build_image"):
        raise click.UsageError("Missing required parameter --build-image.")


def _check_experimental_flag(hook_package_id, command_name, opts):
    # check beta-feature
    beta_features = opts.get("beta_features")

    # check if beta feature flag is required for a specific hook package
    # The IaCs support experimental flag map will contain only the beta IaCs. In case we support the external
    # hooks, we need to first know that the hook package is an external, and to handle the beta feature of it
    # using different approach
    experimental_entry = ExperimentalFlag.IaCsSupport.get(hook_package_id)
    if beta_features is None and experimental_entry is not None:
        iac_support_message = _get_iac_support_experimental_prompt_message(hook_package_id, command_name)
        if not prompt_experimental(experimental_entry, iac_support_message):
            LOG.debug("Experimental flag is disabled and prepare hook is not run")
            return False
    elif not beta_features:
        LOG.debug("--beta-feature flag is disabled and prepare hook is not run")
        return False
    elif beta_features:
        LOG.debug("--beta-feature flag is enabled, update the experimental flag.")
        set_experimental(experimental_entry, True)
        update_experimental_context()
    return True


def _get_iac_support_experimental_prompt_message(hook_package_id: str, command: str) -> str:
    """
    return the customer prompt message for a specific hook package.

    Parameters
    ----------
    hook_package_id: str
        the hook package id to determine what is the supported iac

    command: str
        the current sam command
    Returns
    -------
    str
        the customer prompt message for a specific IaC.
    """

    supported_iacs_messages = {
        "terraform": (
            "Supporting Terraform applications is a beta feature.\n"
            "Please confirm if you would like to proceed using AWS SAM CLI with terraform application.\n"
            f"You can also enable this beta feature with 'sam {command} --beta-features'."
        )
    }
    return supported_iacs_messages.get(hook_package_id, "")
