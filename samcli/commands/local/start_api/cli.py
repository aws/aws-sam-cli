"""
CLI command for "local start-api" command
"""

import logging
import click

from samcli.cli.main import pass_context, common_options as cli_framework_options, aws_creds_options
from samcli.commands.local.cli_common.options import (
    invoke_common_options,
    service_common_options,
    warm_containers_common_options,
    local_common_options,
)
from samcli.commands.local.lib.exceptions import InvalidIntermediateImageError
from samcli.lib.telemetry.metric import track_command
from samcli.cli.cli_config_file import configuration_option, TomlProvider
from samcli.lib.utils.version_checker import check_newer_version
from samcli.local.docker.exceptions import ContainerNotStartableException

LOG = logging.getLogger(__name__)

HELP_TEXT = """
Allows you to run your Serverless application locally for quick development & testing.
 When run in a directory that contains your Serverless functions and your AWS SAM template, it will create a local HTTP
 server hosting all of your functions. When accessed (via browser, cli etc), it will launch a Docker container locally
 to invoke the function. It will read the CodeUri property of AWS::Serverless::Function resource to find the path in
 your file system containing the Lambda Function code. This could be the project's root directory for interpreted
 languages like Node & Python, or a build directory that stores your compiled artifacts or a JAR file. If you are using
 a interpreted language, local changes will be available immediately in Docker container on every invoke. For more
 compiled languages or projects requiring complex packing support, we recommended you run your own building solution
and point SAM to the directory or file containing build artifacts.
"""


@click.command(
    "start-api",
    help=HELP_TEXT,
    short_help="Sets up a local endpoint you can use to test your API. Supports hot-reloading "
    "so you don't need to restart this service when you make changes to your function.",
)
@configuration_option(provider=TomlProvider(section="parameters"))
@service_common_options(3000)
@click.option(
    "--static-dir",
    "-s",
    default="public",
    help="Any static assets (e.g. CSS/Javascript/HTML) files located in this directory " "will be presented at /",
)
@invoke_common_options
@warm_containers_common_options
@local_common_options
@cli_framework_options
@aws_creds_options  # pylint: disable=R0914
@pass_context
@track_command
@check_newer_version
def cli(
    ctx,
    # start-api Specific Options
    host,
    port,
    static_dir,
    # Common Options for Lambda Invoke
    template_file,
    env_vars,
    debug_port,
    debug_args,
    debugger_path,
    container_env_vars,
    docker_volume_basedir,
    docker_network,
    log_file,
    layer_cache_basedir,
    skip_pull_image,
    force_image_build,
    parameter_overrides,
    config_file,
    config_env,
    warm_containers,
    shutdown,
    debug_function,
):
    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing

    do_cli(
        ctx,
        host,
        port,
        static_dir,
        template_file,
        env_vars,
        debug_port,
        debug_args,
        debugger_path,
        container_env_vars,
        docker_volume_basedir,
        docker_network,
        log_file,
        layer_cache_basedir,
        skip_pull_image,
        force_image_build,
        parameter_overrides,
        warm_containers,
        shutdown,
        debug_function,
    )  # pragma: no cover


def do_cli(  # pylint: disable=R0914
    ctx,
    host,
    port,
    static_dir,
    template,
    env_vars,
    debug_port,
    debug_args,
    debugger_path,
    container_env_vars,
    docker_volume_basedir,
    docker_network,
    log_file,
    layer_cache_basedir,
    skip_pull_image,
    force_image_build,
    parameter_overrides,
    warm_containers,
    shutdown,
    debug_function,
):
    """
    Implementation of the ``cli`` method, just separated out for unit testing purposes
    """

    from samcli.commands.local.cli_common.invoke_context import InvokeContext
    from samcli.commands.local.lib.exceptions import NoApisDefined
    from samcli.lib.providers.exceptions import InvalidLayerReference
    from samcli.commands.exceptions import UserException
    from samcli.commands.local.lib.local_api_service import LocalApiService
    from samcli.commands.validate.lib.exceptions import InvalidSamDocumentException
    from samcli.commands.local.lib.exceptions import OverridesNotWellDefinedError
    from samcli.local.docker.lambda_debug_settings import DebuggingNotSupported

    LOG.debug("local start-api command is called")

    # Pass all inputs to setup necessary context to invoke function locally.
    # Handler exception raised by the processor for invalid args and print errors

    try:
        with InvokeContext(
            template_file=template,
            function_identifier=None,  # Don't scope to one particular function
            env_vars_file=env_vars,
            docker_volume_basedir=docker_volume_basedir,
            docker_network=docker_network,
            log_file=log_file,
            skip_pull_image=skip_pull_image,
            debug_ports=debug_port,
            debug_args=debug_args,
            debugger_path=debugger_path,
            container_env_vars_file=container_env_vars,
            parameter_overrides=parameter_overrides,
            layer_cache_basedir=layer_cache_basedir,
            force_image_build=force_image_build,
            aws_region=ctx.region,
            aws_profile=ctx.profile,
            warm_container_initialization_mode=warm_containers,
            debug_function=debug_function,
            shutdown=shutdown,
        ) as invoke_context:

            service = LocalApiService(lambda_invoke_context=invoke_context, port=port, host=host, static_dir=static_dir)
            service.start()

    except NoApisDefined as ex:
        raise UserException(
            "Template does not have any APIs connected to Lambda functions", wrapped_from=ex.__class__.__name__
        ) from ex
    except (
        InvalidSamDocumentException,
        OverridesNotWellDefinedError,
        InvalidLayerReference,
        InvalidIntermediateImageError,
        DebuggingNotSupported,
    ) as ex:
        raise UserException(str(ex), wrapped_from=ex.__class__.__name__) from ex
    except ContainerNotStartableException as ex:
        raise UserException(str(ex), wrapped_from=ex.__class__.__name__) from ex
