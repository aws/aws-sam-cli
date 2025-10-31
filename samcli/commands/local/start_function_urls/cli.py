"""
CLI command for "local start-function-urls" command
"""

import logging

import click

from samcli.cli.cli_config_file import ConfigProvider, configuration_option
from samcli.cli.main import aws_creds_options, pass_context, print_cmdline_args
from samcli.cli.main import common_options as cli_framework_options
from samcli.commands._utils.experimental import force_experimental
from samcli.commands._utils.option_value_processor import process_image_options
from samcli.commands.local.cli_common.options import (
    invoke_common_options,
    local_common_options,
    warm_containers_common_options,
)
from samcli.commands.local.start_function_urls.core.command import InvokeFunctionUrlsCommand
from samcli.lib.telemetry.metric import track_command
from samcli.lib.utils.version_checker import check_newer_version

LOG = logging.getLogger(__name__)

HELP_TEXT = """
Run Lambda functions with Function URLs locally for testing.
Each function gets its own port, matching AWS production behavior.
"""

DESCRIPTION = """
  Allows you to run Lambda functions with Function URLs locally for quick development & testing.
  When run in a directory that contains Lambda functions with FunctionUrlConfig in the SAM template,
  it will create local HTTP servers for each function on separate ports.
  
  Each function URL serves from the root path (/), matching AWS production behavior where
  each Function URL has its own unique domain. This port-based approach maintains production
  parity while enabling local testing.
"""


@click.command(
    "start-function-urls",
    cls=InvokeFunctionUrlsCommand,
    help=HELP_TEXT,
    short_help=HELP_TEXT,
    description=DESCRIPTION,
    requires_credentials=False,
    context_settings={"max_content_width": 120},
)
@force_experimental
@configuration_option(provider=ConfigProvider(section="parameters"))
@click.option(
    "--host",
    default="127.0.0.1",
    help="Local hostname or IP address to bind to (default: 127.0.0.1)",
)
@click.option(
    "--port-range",
    default="3001-3010",
    help="Port range for auto-assignment (e.g., 3001-3010)",
)
@click.option(
    "--function-name",
    help="Start specific function only",
)
@click.option(
    "--port",
    type=int,
    help="Specific port for single function (requires --function-name)",
)
@click.option(
    "--disable-authorizer",
    is_flag=True,
    default=False,
    help="Disable IAM authorization checks for development",
)
@invoke_common_options
@warm_containers_common_options
@local_common_options
@cli_framework_options
@aws_creds_options
@pass_context
@track_command
@check_newer_version
@print_cmdline_args
def cli(
    ctx,
    # Function URLs specific options
    host,
    port_range,
    function_name,
    port,
    disable_authorizer,
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
    container_host,
    container_host_interface,
    add_host,
    invoke_image,
    no_memory_limit,
):
    """
    `sam local start-function-urls` command entry point
    """
    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing
    do_cli(
        ctx,
        host,
        port_range,
        function_name,
        port,
        disable_authorizer,
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
        container_host,
        container_host_interface,
        add_host,
        invoke_image,
        no_memory_limit,
    )


def do_cli(
    ctx,
    host,
    port_range,
    function_name,
    port,
    disable_authorizer,
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
    container_host,
    container_host_interface,
    add_host,
    invoke_image,
    no_mem_limit,
):
    """
    Implementation of the ``cli`` method
    """
    from samcli.commands.exceptions import UserException
    from samcli.commands.local.cli_common.invoke_context import DockerIsNotReachableException, InvokeContext
    from samcli.commands.local.lib.exceptions import NoFunctionUrlsDefined, OverridesNotWellDefinedError
    from samcli.commands.local.lib.local_function_url_service import LocalFunctionUrlService
    from samcli.commands.validate.lib.exceptions import InvalidSamDocumentException

    LOG.debug("local start-function-urls command is called")

    processed_invoke_images = process_image_options(invoke_image)

    # Parse port range
    if "-" in port_range:
        start_port, end_port = map(int, port_range.split("-"))
    else:
        start_port = int(port_range)
        end_port = start_port + 10

    try:
        with InvokeContext(
            template_file=template,
            function_identifier=None,
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
            aws_region=ctx.region if ctx else None,
            aws_profile=ctx.profile if ctx else None,
            warm_container_initialization_mode=warm_containers,
            debug_function=debug_function,
            shutdown=shutdown,
            container_host=container_host,
            container_host_interface=container_host_interface,
            add_host=add_host,
            invoke_images=processed_invoke_images,
            no_mem_limit=no_mem_limit,
        ) as invoke_context:
            # Create Function URL service
            service = LocalFunctionUrlService(
                lambda_invoke_context=invoke_context,
                port_range=(start_port, end_port),
                host=host,
                disable_authorizer=disable_authorizer,
            )

            # Start the service
            if function_name:
                # Start specific function (with optional specific port)
                service.start(function_name=function_name, port=port)
            else:
                # Start all functions
                service.start()

    except NoFunctionUrlsDefined as ex:
        raise UserException(str(ex)) from ex
    except DockerIsNotReachableException as ex:
        raise UserException(str(ex), wrapped_from=ex.__class__.__name__) from ex
    except (InvalidSamDocumentException, OverridesNotWellDefinedError) as ex:
        raise UserException(str(ex)) from ex
    except KeyboardInterrupt:
        LOG.info("Keyboard interrupt received")
    except Exception as ex:
        raise UserException(
            f"Error starting Function URL services: {str(ex)}", wrapped_from=ex.__class__.__name__
        ) from ex
