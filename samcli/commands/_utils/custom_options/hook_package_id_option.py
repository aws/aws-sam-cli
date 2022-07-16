"""
Custom Click options for hook package id
"""

import logging
import os
import click

from samcli.commands._utils.options import DEFAULT_BUILT_TEMPLATE_PATH
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
        if self.name in opts:
            # validate the hook_package_id value exists
            hook_package_id = opts[self.name]
            iac_hook_wrapper = None
            try:
                iac_hook_wrapper = IacHookWrapper(hook_package_id)
            except InvalidHookWrapperException as e:
                raise click.BadParameter(
                    f"{hook_package_id} is not a valid hook package id. This is the list of valid "
                    f"packages ids {get_available_hook_packages_ids()}"
                ) from e

            # validate coexist options
            for invalid_opt in self._invalid_coexist_options:
                invalid_opt_name = invalid_opt.replace("-", "_")
                if invalid_opt_name in opts:
                    raise click.BadParameter(
                        f"Parameters {opt_name}, and {','.join(self._invalid_coexist_options)} could not be used "
                        f"together"
                    )

            # call prepare hook
            built_template_path = DEFAULT_BUILT_TEMPLATE_PATH
            if not self._force_prepare and os.path.exists(built_template_path):
                LOG.info("Skip Running Prepare hook. The current application is already prepared.")
            else:
                LOG.info("Running Prepare Hook to prepare the current application")

                output_dir_path = os.path.join(".aws-sam", "iacs_metadata")
                iac_project_path = os.getcwd()
                debug = opts.get("debug", False)
                aws_profile = opts.get("profile")
                aws_region = opts.get("region")
                metadata_file = iac_hook_wrapper.prepare(
                    output_dir_path, iac_project_path, debug, aws_profile, aws_region
                )

                LOG.info("Prepare Hook is done, and metadata file generated at %s", metadata_file)
                opts["template_file"] = metadata_file
        return super().handle_parse_result(ctx, opts, args)
