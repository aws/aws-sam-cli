"""
CLI command for "build" command
"""

import os
import logging
from typing import List, Optional, Dict, Tuple
import click

from samcli.cli.context import Context
from samcli.commands._utils.options import (
    template_option_without_build,
    docker_common_options,
    parameter_override_option,
)
from samcli.cli.main import pass_context, common_options as cli_framework_options, aws_creds_options, print_cmdline_args
from samcli.lib.build.exceptions import BuildInsideContainerError
from samcli.lib.providers.sam_stack_provider import SamLocalStackProvider
from samcli.lib.telemetry.metric import track_command
from samcli.cli.cli_config_file import configuration_option, TomlProvider
from samcli.lib.utils.version_checker import check_newer_version
from samcli.commands.build.exceptions import InvalidBuildImageException
from samcli.commands.build.click_container import ContainerOptions

LOG = logging.getLogger(__name__)

DEFAULT_BUILD_DIR = os.path.join(".aws-sam", "build")
DEFAULT_CACHE_DIR = os.path.join(".aws-sam", "cache")

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
1. Python 2.7, 3.6, 3.7, 3.8 3.9 using PIP\n
2. Nodejs 14.x, 12.x, 10.x, 8.10, 6.10 using NPM\n
3. Ruby 2.5 using Bundler\n
4. Java 8, Java 11 using Gradle and Maven\n
5. Dotnetcore2.0 and 2.1 using Dotnet CLI (without --use-container flag)\n
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
    "--build-dir",
    "-b",
    default=DEFAULT_BUILD_DIR,
    type=click.Path(file_okay=False, dir_okay=True, writable=True),  # Must be a directory
    help="Path to a folder where the built artifacts will be stored. "
    "This directory will be first removed before starting a build.",
)
@click.option(
    "--cache-dir",
    "-cd",
    default=DEFAULT_CACHE_DIR,
    type=click.Path(file_okay=False, dir_okay=True, writable=True),  # Must be a directory
    help="The folder where the cache artifacts will be stored when --cached is specified. "
    "The default cache directory is .aws-sam/cache",
)
@click.option(
    "--base-dir",
    "-s",
    default=None,
    type=click.Path(dir_okay=True, file_okay=False),  # Must be a directory
    help="Resolve relative paths to function's source code with respect to this folder. Use this if "
    "SAM template and your source code are not in same enclosing folder. By default, relative paths "
    "are resolved with respect to the SAM template's location",
)
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
@click.option(
    "--manifest",
    "-m",
    default=None,
    type=click.Path(),
    help="Path to a custom dependency manifest (e.g., package.json) to use instead of the default one",
)
@click.option(
    "--cached",
    "-c",
    is_flag=True,
    help="Enable cached builds. Use this flag to reuse build artifacts that have not changed from previous builds. "
    "AWS SAM evaluates whether you have made any changes to files in your project directory. \n\n"
    "Note: AWS SAM does not evaluate whether changes have been made to third party modules "
    "that your project depends on, where you have not provided a specific version. "
    "For example, if your Python function includes a requirements.txt file with the following entry "
    "requests=1.x and the latest request module version changes from 1.1 to 1.2, "
    "SAM will not pull the latest version until you run a non-cached build.",
)
@template_option_without_build
@parameter_override_option
@docker_common_options
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

    from samcli.commands.exceptions import UserException

    from samcli.commands.build.build_context import BuildContext
    from samcli.lib.build.app_builder import (
        ApplicationBuilder,
        BuildError,
        UnsupportedBuilderLibraryVersionError,
        ContainerBuildNotSupported,
    )
    from samcli.lib.build.workflow_config import UnsupportedRuntimeException
    from samcli.local.lambdafn.exceptions import FunctionNotFound
    from samcli.commands._utils.template import move_template
    from samcli.lib.build.build_graph import InvalidBuildGraphException

    LOG.debug("'build' command is called")
    if cached:
        LOG.info("Starting Build use cache")
    if use_container:
        LOG.info("Starting Build inside a container")

    processed_env_vars = _process_env_var(container_env_var)
    processed_build_images = _process_image_options(build_image)

    with BuildContext(
        function_identifier,
        template,
        base_dir,
        build_dir,
        cache_dir,
        cached,
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
        try:
            builder = ApplicationBuilder(
                ctx.resources_to_build,
                ctx.build_dir,
                ctx.base_dir,
                ctx.cache_dir,
                ctx.cached,
                ctx.is_building_specific_resource,
                manifest_path_override=ctx.manifest_path_override,
                container_manager=ctx.container_manager,
                mode=ctx.mode,
                parallel=parallel,
                container_env_var=processed_env_vars,
                container_env_var_file=container_env_var_file,
                build_images=processed_build_images,
            )
        except FunctionNotFound as ex:
            raise UserException(str(ex), wrapped_from=ex.__class__.__name__) from ex

        try:
            artifacts = builder.build()
            stack_output_template_path_by_stack_path = {
                stack.stack_path: stack.get_output_template_path(ctx.build_dir) for stack in ctx.stacks
            }
            for stack in ctx.stacks:
                modified_template = builder.update_template(
                    stack,
                    artifacts,
                    stack_output_template_path_by_stack_path,
                )
                move_template(stack.location, stack.get_output_template_path(ctx.build_dir), modified_template)

            click.secho("\nBuild Succeeded", fg="green")

            # try to use relpath so the command is easier to understand, however,
            # under Windows, when SAM and (build_dir or output_template_path) are
            # on different drive, relpath() fails.
            root_stack = SamLocalStackProvider.find_root_stack(ctx.stacks)
            out_template_path = root_stack.get_output_template_path(ctx.build_dir)
            try:
                build_dir_in_success_message = os.path.relpath(ctx.build_dir)
                output_template_path_in_success_message = os.path.relpath(out_template_path)
            except ValueError:
                LOG.debug("Failed to retrieve relpath - using the specified path as-is instead")
                build_dir_in_success_message = ctx.build_dir
                output_template_path_in_success_message = out_template_path

            msg = gen_success_msg(
                build_dir_in_success_message,
                output_template_path_in_success_message,
                os.path.abspath(ctx.build_dir) == os.path.abspath(DEFAULT_BUILD_DIR),
            )

            click.secho(msg, fg="yellow")

        except (
            UnsupportedRuntimeException,
            BuildError,
            BuildInsideContainerError,
            UnsupportedBuilderLibraryVersionError,
            ContainerBuildNotSupported,
            InvalidBuildGraphException,
        ) as ex:
            click.secho("\nBuild Failed", fg="red")

            # Some Exceptions have a deeper wrapped exception that needs to be surfaced
            # from deeper than just one level down.
            deep_wrap = getattr(ex, "wrapped_from", None)
            wrapped_from = deep_wrap if deep_wrap else ex.__class__.__name__
            raise UserException(str(ex), wrapped_from=wrapped_from) from ex


def gen_success_msg(artifacts_dir: str, output_template_path: str, is_default_build_dir: bool) -> str:

    invoke_cmd = "sam local invoke"
    if not is_default_build_dir:
        invoke_cmd += " -t {}".format(output_template_path)

    deploy_cmd = "sam deploy --guided"
    if not is_default_build_dir:
        deploy_cmd += " --template-file {}".format(output_template_path)

    msg = """\nBuilt Artifacts  : {artifacts_dir}
Built Template   : {template}

Commands you can use next
=========================
[*] Invoke Function: {invokecmd}
[*] Deploy: {deploycmd}
    """.format(
        invokecmd=invoke_cmd, deploycmd=deploy_cmd, artifacts_dir=artifacts_dir, template=output_template_path
    )

    return msg


def _get_mode_value_from_envvar(name: str, choices: List[str]) -> Optional[str]:

    mode = os.environ.get(name, None)
    if not mode:
        return None

    if mode not in choices:
        raise click.UsageError("Invalid value for 'mode': invalid choice: {}. (choose from {})".format(mode, choices))

    return mode


def _process_env_var(container_env_var: Optional[Tuple[str]]) -> Dict:
    """
    Parameters
    ----------
    container_env_var : Tuple
        the tuple of command line env vars received from --container-env-var flag
        Each input format needs to be either function specific format (FuncName.VarName=Value)
        or global format (VarName=Value)

    Returns
    -------
    dictionary
        Processed command line environment variables
    """
    processed_env_vars: Dict = {}

    if container_env_var:
        for env_var in container_env_var:
            location_key = "Parameters"

            env_var_name, value = _parse_key_value_pair(env_var)

            if not env_var_name or not value:
                LOG.error("Invalid command line --container-env-var input %s, skipped", env_var)
                continue

            if "." in env_var_name:
                location_key, env_var_name = env_var_name.split(".", 1)
                if not location_key.strip() or not env_var_name.strip():
                    LOG.error("Invalid command line --container-env-var input %s, skipped", env_var)
                    continue

            if not processed_env_vars.get(location_key):
                processed_env_vars[location_key] = {}
            processed_env_vars[location_key][env_var_name] = value

    return processed_env_vars


def _process_image_options(image_args: Optional[Tuple[str]]) -> Dict:
    """
    Parameters
    ----------
    image_args : Tuple
        Tuple of command line image options in the format of
        "Function1=public.ecr.aws/abc/abc:latest" or
        "public.ecr.aws/abc/abc:latest"

    Returns
    -------
    dictionary
        Function as key and the corresponding image URI as value.
        Global default image URI is contained in the None key.
    """
    build_images: Dict[Optional[str], str] = dict()
    if image_args:
        for build_image_string in image_args:
            function_name, image_uri = _parse_key_value_pair(build_image_string)
            if not image_uri:
                raise InvalidBuildImageException(f"Invalid command line --build-image input {build_image_string}.")
            build_images[function_name] = image_uri

    return build_images


def _parse_key_value_pair(arg: str) -> Tuple[Optional[str], str]:
    """
    Parameters
    ----------
    arg : str
        Arg in the format of "Value" or "Key=Value"
    Returns
    -------
    key : Optional[str]
        If key is not specified, None will be the key.
    value : str
    """
    key: Optional[str]
    value: str
    if "=" in arg:
        parts = arg.split("=", 1)
        key = parts[0].strip()
        value = parts[1].strip()
    else:
        key = None
        value = arg.strip()
    return key, value
