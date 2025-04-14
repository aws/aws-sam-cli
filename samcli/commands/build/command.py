"""
CLI command for "build" command
"""

import logging
import os
from typing import Dict, List, Optional, Tuple

import click

from samcli.cli.cli_config_file import ConfigProvider, configuration_option, save_params_option
from samcli.cli.context import Context
from samcli.cli.main import aws_creds_options, pass_context, print_cmdline_args
from samcli.cli.main import common_options as cli_framework_options
from samcli.commands._utils.option_value_processor import process_env_var, process_image_options
from samcli.commands._utils.options import (
    base_dir_option,
    build_dir_option,
    build_image_option,
    build_in_source_option,
    cache_dir_option,
    cached_option,
    container_env_var_file_option,
    docker_common_options,
    hook_name_click_option,
    manifest_option,
    mount_symlinks_option,
    parameter_override_option,
    skip_prepare_infra_option,
    template_option_without_build,
    terraform_project_root_path_option,
    use_container_build_option,
)
from samcli.commands.build.click_container import ContainerOptions
from samcli.commands.build.core.command import BuildCommand
from samcli.commands.build.utils import MountMode
from samcli.lib.telemetry.metric import track_command
from samcli.lib.utils.version_checker import check_newer_version

LOG = logging.getLogger(__name__)

HELP_TEXT = """
    Build AWS serverless function code.
"""

DESCRIPTION = """
  Build AWS serverless function code to generate artifacts targeting
  AWS Lambda execution environment.\n
  \b
  Supported Resource Types
  ------------------------
  1. AWS::Serverless::Function\n
  2. AWS::Lambda::Function\n
  3. AWS::Serverless::LayerVersion\n
  4. AWS::Lambda::LayerVersion\n
  \b
  Supported Runtimes
  ------------------
  1. Python 3.8, 3.9, 3.10, 3.11, 3.12, 3.13 using PIP\n
  2. Nodejs 22.x, Nodejs 20.x, 18.x, 16.x, 14.x, 12.x using NPM\n
  3. Ruby 3.2, 3.3, 3.4 using Bundler\n
  4. Java 8, Java 11, Java 17, Java 21 using Gradle and Maven\n
  5. Dotnet8, Dotnet6 using Dotnet CLI\n
  6. Go 1.x using Go Modules (without --use-container)\n
"""


@click.command(
    "build",
    cls=BuildCommand,
    help=HELP_TEXT,
    description=DESCRIPTION,
    requires_credentials=False,
    short_help=HELP_TEXT,
    context_settings={"max_content_width": 120},
)
@configuration_option(provider=ConfigProvider(section="parameters"))
@terraform_project_root_path_option
@hook_name_click_option(
    force_prepare=True,
    invalid_coexist_options=["t", "template-file", "template", "parameter-overrides", "build-in-source"],
)
@skip_prepare_infra_option
@use_container_build_option
@build_in_source_option
@click.option(
    "--container-env-var",
    "-e",
    default=None,
    multiple=True,  # Can pass in multiple env vars
    required=False,
    help="Environment variables to be passed into build containers"
    "\nResource format (FuncName.VarName=Value) or Global format (VarName=Value)."
    "\n\n Example: --container-env-var Func1.VAR1=value1 --container-env-var VAR2=value2",
    cls=ContainerOptions,
)
@container_env_var_file_option(cls=ContainerOptions)
@build_image_option(cls=ContainerOptions)
@click.option(
    "--exclude",
    "-x",
    default=None,
    multiple=True,  # Multiple resources can be excepted from the build
    help="Name of the resource(s) to exclude from AWS SAM CLI build.",
)
@click.option(
    "--parallel", "-p", is_flag=True, help="Enable parallel builds for AWS SAM template's functions and layers."
)
@click.option(
    "--mount-with",
    "-mw",
    type=click.Choice(MountMode.values(), case_sensitive=False),
    default=MountMode.READ.value,
    help="Specify mount mode for building functions/layers inside container. "
    "If it is mounted with write permissions, some files in source code directory may "
    "be changed/added by the build process. By default the source code directory is read only.",
    cls=ContainerOptions,
)
@mount_symlinks_option
@build_dir_option
@cache_dir_option
@base_dir_option
@manifest_option
@cached_option
@template_option_without_build
@parameter_override_option
@docker_common_options
@cli_framework_options
@aws_creds_options
@click.argument("resource_logical_id", required=False)
@save_params_option
@pass_context
@track_command
@check_newer_version
@print_cmdline_args
def cli(
    ctx: Context,
    # please keep the type below consistent with @click.options
    resource_logical_id: Optional[str],
    template_file: str,
    base_dir: Optional[str],
    build_dir: str,
    cache_dir: str,
    use_container: bool,
    cached: bool,
    parallel: bool,
    manifest: Optional[str],
    docker_network: Optional[str],
    container_env_var: Optional[Tuple[str]],
    container_env_var_file: Optional[str],
    build_image: Optional[Tuple[str]],
    exclude: Optional[Tuple[str, ...]],
    skip_pull_image: bool,
    parameter_overrides: dict,
    config_file: str,
    config_env: str,
    save_params: bool,
    hook_name: Optional[str],
    skip_prepare_infra: bool,
    mount_with: str,
    terraform_project_root_path: Optional[str],
    build_in_source: Optional[bool],
    mount_symlinks: Optional[bool],
) -> None:
    """
    `sam build` command entry point
    """
    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing

    mode = _get_mode_value_from_envvar("SAM_BUILD_MODE", choices=["debug"])

    do_cli(
        ctx,
        resource_logical_id,
        template_file,
        base_dir,
        build_dir,
        cache_dir,
        True,
        use_container,
        cached,
        parallel,
        manifest,
        docker_network,
        skip_pull_image,
        parameter_overrides,
        mode,
        container_env_var,
        container_env_var_file,
        build_image,
        exclude,
        hook_name,
        build_in_source,
        mount_with,
        mount_symlinks,
    )  # pragma: no cover


def do_cli(  # pylint: disable=too-many-locals, too-many-statements
    click_ctx,
    function_identifier: Optional[str],
    template: str,
    base_dir: Optional[str],
    build_dir: str,
    cache_dir: str,
    clean: bool,
    use_container: bool,
    cached: bool,
    parallel: bool,
    manifest_path: Optional[str],
    docker_network: Optional[str],
    skip_pull_image: bool,
    parameter_overrides: Dict,
    mode: Optional[str],
    container_env_var: Optional[Tuple[str]],
    container_env_var_file: Optional[str],
    build_image: Optional[Tuple[str]],
    exclude: Optional[Tuple[str, ...]],
    hook_name: Optional[str],
    build_in_source: Optional[bool],
    mount_with: str,
    mount_symlinks: Optional[bool],
) -> None:
    """
    Implementation of the ``cli`` method
    """

    from samcli.commands.build.build_context import BuildContext

    LOG.debug("'build' command is called")
    if cached:
        LOG.info("Starting Build use cache")
    if use_container:
        LOG.info("Starting Build inside a container")

    processed_env_vars = process_env_var(container_env_var)
    processed_build_images = process_image_options(build_image)

    with BuildContext(
        function_identifier,
        template,
        base_dir,
        build_dir,
        cache_dir,
        cached,
        parallel=parallel,
        clean=clean,
        manifest_path=manifest_path,
        use_container=use_container,
        parameter_overrides=parameter_overrides,
        docker_network=docker_network,
        skip_pull_image=skip_pull_image,
        mode=mode,
        container_env_var=processed_env_vars,
        container_env_var_file=container_env_var_file,
        build_images=processed_build_images,
        excluded_resources=exclude,
        aws_region=click_ctx.region,
        hook_name=hook_name,
        build_in_source=build_in_source,
        mount_with=mount_with,
        mount_symlinks=mount_symlinks,
    ) as ctx:
        ctx.run()


def _get_mode_value_from_envvar(name: str, choices: List[str]) -> Optional[str]:
    mode = os.environ.get(name, None)
    if not mode:
        return None

    if mode not in choices:
        raise click.UsageError("Invalid value for 'mode': invalid choice: {}. (choose from {})".format(mode, choices))

    return mode
