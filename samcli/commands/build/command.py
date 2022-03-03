"""
CLI command for "build" command
"""

import os
import logging
from typing import List, Optional, Dict, Tuple
import click

from samcli.cli.context import Context
from samcli.commands._utils.experimental import experimental
from samcli.commands._utils.options import (
    template_option_without_build,
    docker_common_options,
    parameter_override_option,
    build_dir_option,
    cache_dir_option,
    base_dir_option,
    manifest_option,
    cached_option,
)
from samcli.commands._utils.option_value_processor import process_env_var, process_image_options
from samcli.cli.main import pass_context, common_options as cli_framework_options, aws_creds_options, print_cmdline_args
from samcli.lib.telemetry.metric import track_command
from samcli.cli.cli_config_file import configuration_option, TomlProvider
from samcli.lib.utils.version_checker import check_newer_version
from samcli.commands.build.click_container import ContainerOptions

LOG = logging.getLogger(__name__)


HELP_TEXT = """
Use this command to build your AWS Lambda Functions source code to generate artifacts that target AWS Lambda's
execution environment.\n
\b
Supported Resource Types
------------------------
1. AWS::Serverless::Function\n
2. AWS::Lambda::Function\n
\b
Supported Runtimes
------------------
1. Python 3.6, 3.7, 3.8 3.9 using PIP\n
2. Nodejs 14.x, 12.x using NPM\n
3. Ruby 2.7 using Bundler\n
4. Java 8, Java 11 using Gradle and Maven\n
5. Dotnetcore3.1, Dotnet6 using Dotnet CLI (without --use-container flag)\n
6. Go 1.x using Go Modules (without --use-container flag)\n
\b
Examples
--------
To use this command, update your SAM template to specify the path
to your function's source code in the resource's Code or CodeUri property.
\b
To build on your workstation, run this command in folder containing
SAM template. Built artifacts will be written to .aws-sam/build folder
$ sam build\n
\b
To build inside a AWS Lambda like Docker container
$ sam build --use-container
\b
To build with inline environment variables passed inside build containers
$ sam build --use-container --container-env-var Function.ENV_VAR=value --container-env-var GLOBAL_ENV_VAR=value
\b
To build with environment variables file passd inside build containers
$ sam build --use-container --container-env-var-file env.json
\b
To build & run your functions locally
$ sam build && sam local invoke
\b
To build and package for deployment
$ sam build && sam package --s3-bucket <bucketname>
\b
To build only an individual resource (function or layer) located in the SAM
template. Downstream SAM package and deploy will deploy only this resource
$ sam build MyFunction
"""


@click.command("build", help=HELP_TEXT, short_help="Build your Lambda function code")
@configuration_option(provider=TomlProvider(section="parameters"))
@click.option(
    "--use-container",
    "-u",
    is_flag=True,
    help="If your functions depend on packages that have natively compiled dependencies, use this flag "
    "to build your function inside an AWS Lambda-like Docker container",
)
@click.option(
    "--container-env-var",
    "-e",
    default=None,
    multiple=True,  # Can pass in multiple env vars
    required=False,
    help="Input environment variables through command line to pass into build containers, you can either "
    "input function specific format (FuncName.VarName=Value) or global format (VarName=Value). e.g., "
    "sam build --use-container --container-env-var Func1.VAR1=value1 --container-env-var VAR2=value2",
    cls=ContainerOptions,
)
@click.option(
    "--container-env-var-file",
    "-ef",
    default=None,
    type=click.Path(),  # Must be a json file
    help="Path to environment variable json file (e.g., env_vars.json) to pass into build containers",
    cls=ContainerOptions,
)
@click.option(
    "--build-image",
    "-bi",
    default=None,
    multiple=True,  # Can pass in multiple build images
    required=False,
    help="Container image URIs for building functions/layers. "
    "You can specify for all functions/layers with just the image URI "
    "(--build-image public.ecr.aws/sam/build-nodejs14.x:latest). "
    "You can specify for each individual function with "
    "(--build-image FunctionLogicalID=public.ecr.aws/sam/build-nodejs14.x:latest). "
    "A combination of the two can be used. If a function does not have build image specified or "
    "an image URI for all functions, the default SAM CLI build images will be used.",
    cls=ContainerOptions,
)
@click.option(
    "--parallel",
    "-p",
    is_flag=True,
    help="Enabled parallel builds. Use this flag to build your AWS SAM template's functions and layers in parallel. "
    "By default the functions and layers are built in sequence",
)
@build_dir_option
@cache_dir_option
@base_dir_option
@manifest_option
@cached_option
@template_option_without_build
@parameter_override_option
@docker_common_options
@experimental
@cli_framework_options
@aws_creds_options
@click.argument("resource_logical_id", required=False)
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
    skip_pull_image: bool,
    parameter_overrides: dict,
    config_file: str,
    config_env: str,
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
        aws_region=click_ctx.region,
    ) as ctx:
        ctx.run()


def _get_mode_value_from_envvar(name: str, choices: List[str]) -> Optional[str]:

    mode = os.environ.get(name, None)
    if not mode:
        return None

    if mode not in choices:
        raise click.UsageError("Invalid value for 'mode': invalid choice: {}. (choose from {})".format(mode, choices))

    return mode
