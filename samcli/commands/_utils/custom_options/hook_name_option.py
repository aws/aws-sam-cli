"""
Custom Click options for hook name
"""

import logging
import os
from typing import Any, Mapping

import click

from samcli.cli.context import Context
from samcli.cli.global_config import GlobalConfig
from samcli.commands._utils.constants import DEFAULT_BUILT_TEMPLATE_PATH
from samcli.commands._utils.experimental import (
    ExperimentalFlag,
    prompt_experimental,
    set_experimental,
    update_experimental_context,
)
from samcli.lib.hook.exceptions import InvalidHookWrapperException
from samcli.lib.hook.hook_wrapper import IacHookWrapper, get_available_hook_packages_ids
from samcli.lib.telemetry.event import EventName, EventTracker

LOG = logging.getLogger(__name__)

PLAN_FILE_OPTION = "terraform_plan_file"


class HookNameOption(click.Option):
    """
    A custom option class that allows do custom validation for the SAM CLI commands options in case if hook name
    is passed. It also calls the correct IaC prepare hook, and update the SAM CLI commands options based on the
    prepare hook output.
    """

    def __init__(self, *args, **kwargs):
        self.hook_name_option_name = "hook_name"
        self._force_prepare = kwargs.pop("force_prepare", True)
        self._invalid_coexist_options = kwargs.pop("invalid_coexist_options", [])
        super().__init__(*args, **kwargs)

    def handle_parse_result(self, ctx, opts, args):
        opt_name = self.hook_name_option_name.replace("_", "-")
        if self.hook_name_option_name not in opts and self.hook_name_option_name not in ctx.default_map:
            return super().handle_parse_result(ctx, opts, args)
        command_name = ctx.command.name
        if command_name in ["invoke", "start-lambda", "start-api"]:
            command_name = f"local {command_name}"
        # validate the hook_name value exists
        hook_name = opts.get(self.hook_name_option_name) or ctx.default_map[self.hook_name_option_name]
        iac_hook_wrapper = None
        try:
            iac_hook_wrapper = IacHookWrapper(hook_name)
        except InvalidHookWrapperException as e:
            raise click.BadParameter(
                f"{hook_name} is not a valid hook name."
                f"{os.linesep}valid package ids: {get_available_hook_packages_ids()}"
            ) from e

        self._validate_coexist_options(opt_name, opts)

        _validate_build_command_parameters(command_name, opts)

        if not _check_experimental_flag(hook_name, command_name, opts, ctx.default_map):
            return super().handle_parse_result(ctx, opts, args)

        try:
            self._call_prepare_hook(iac_hook_wrapper, opts, ctx)
        except Exception as ex:
            # capture exceptions from prepare hook to emit in track_command
            c = Context.get_current_context()
            c.exception = ex
        finally:
            record_hook_telemetry(opts, ctx)

        return super().handle_parse_result(ctx, opts, args)

    def _call_prepare_hook(self, iac_hook_wrapper, opts, ctx):
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

            debug = _read_parameter_value("debug", opts, ctx, False)
            aws_profile = _read_parameter_value("profile", opts, ctx)
            aws_region = _read_parameter_value("region", opts, ctx)
            skip_prepare_infra = _read_parameter_value("skip_prepare_infra", opts, ctx, False)
            plan_file = _read_parameter_value("terraform_plan_file", opts, ctx)
            project_root_dir = _read_parameter_value("terraform_project_root_path", opts, ctx)

            metadata_file = iac_hook_wrapper.prepare(
                output_dir_path,
                iac_project_path,
                debug,
                aws_profile,
                aws_region,
                skip_prepare_infra,
                plan_file,
                project_root_dir,
            )

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

    # validate that terraform-project-root-path is a parent path of the current directory, or it is a relative path
    project_root_dir = opts.get("terraform_project_root_path")
    if (
        command_name == "build"
        and project_root_dir
        and os.path.isabs(project_root_dir)
        and not os.getcwd().startswith(project_root_dir)
    ):
        LOG.debug(
            f"the provided path {project_root_dir} as terraform project path is not a parent of the current directory "
            f"{os.getcwd()}"
        )
        raise click.UsageError(
            f"{project_root_dir} is not a valid value for Terraform Project Root Path. It should be a parent of the "
            f"current directory that contains the root module of the terraform project."
        )


def _check_experimental_flag(hook_name, command_name, opts, default_map):
    # check beta-feature
    experimental_entry = ExperimentalFlag.IaCsSupport.get(hook_name)
    beta_features = _get_customer_input_beta_features_option(default_map, experimental_entry, opts)

    # check if beta feature flag is required for a specific hook package
    # The IaCs support experimental flag map will contain only the beta IaCs. In case we support the external
    # hooks, we need to first know that the hook package is an external, and to handle the beta feature of it
    # using different approach
    if beta_features is None and experimental_entry is not None:
        iac_support_message = _get_iac_support_experimental_prompt_message(hook_name, command_name)
        if not prompt_experimental(experimental_entry, iac_support_message):
            LOG.debug("Experimental flag is disabled and prepare hook is not run")
            return False
    elif not beta_features:
        LOG.debug("--beta-features flag is disabled and prepare hook is not run")
        return False
    elif beta_features:
        LOG.debug("--beta-features flag is enabled, enabling experimental flag.")
        set_experimental(experimental_entry, True)
        update_experimental_context()
    return True


def _get_customer_input_beta_features_option(default_map, experimental_entry, opts):
    # Get the beta-features flag value from the command parameters if provided.
    beta_features = opts.get("beta_features")
    if beta_features is not None:
        return beta_features

    # Get the beta-features flag value from the SamConfig file if provided.
    beta_features = default_map.get("beta_features")
    if beta_features is not None:
        return beta_features

    # Get the beta-features flag value from the environment variables.
    if experimental_entry:
        gc = GlobalConfig()
        beta_features = gc.get_value(experimental_entry, default=None, value_type=bool, is_flag=True)
        if beta_features is not None:
            return beta_features
        return gc.get_value(ExperimentalFlag.All, default=None, value_type=bool, is_flag=True)

    return None


def _get_iac_support_experimental_prompt_message(hook_name: str, command: str) -> str:
    """
    return the customer prompt message for a specific hook package.

    Parameters
    ----------
    hook_name: str
        the hook name to determine what is the supported iac

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
    return supported_iacs_messages.get(hook_name, "")


def _read_parameter_value(param_name, opts, ctx, default_value=None):
    """
    Read SAM CLI parameter value either from the parameters list or from the samconfig values
    """
    return opts.get(param_name, ctx.default_map.get(param_name, default_value))


def record_hook_telemetry(opts: Mapping[str, Any], ctx: click.Context):
    """
    Emit metrics related to hooks based on the options passed into the command

    Parameters
    ----------
    opts: Mapping[str, Any]
        Mapping between a command line option and its value
    ctx: Context
        Command context properties
    """
    plan_file_param = _read_parameter_value(PLAN_FILE_OPTION, opts, ctx)
    if plan_file_param:
        EventTracker.track_event(EventName.HOOK_CONFIGURATIONS_USED.value, "TerraformPlanFile")
