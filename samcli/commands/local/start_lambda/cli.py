"""
CLI command for "local start-lambda" command
"""

import logging

import click

from samcli.cli.cli_config_file import ConfigProvider, configuration_option, save_params_option
from samcli.cli.main import aws_creds_options, pass_context, print_cmdline_args
from samcli.cli.main import common_options as cli_framework_options
from samcli.commands._utils.option_value_processor import process_image_options
from samcli.commands._utils.options import (
    generate_next_command_recommendation,
    hook_name_click_option,
    skip_prepare_infra_option,
    terraform_plan_file_option,
)
from samcli.commands.local.cli_common.options import (
    invoke_common_options,
    local_common_options,
    service_common_options,
    warm_containers_common_options,
)
from samcli.commands.local.lib.exceptions import InvalidIntermediateImageError
from samcli.commands.local.start_lambda.core.command import InvokeLambdaCommand
from samcli.lib.telemetry.metric import track_command
from samcli.lib.utils.version_checker import check_newer_version
from samcli.local.docker.exceptions import ContainerNotStartableException, PortAlreadyInUse, ProcessSigTermException

LOG = logging.getLogger(__name__)


HELP_TEXT = """
Emulate AWS serverless functions locally.
"""

DESCRIPTION = """
  Programmatically invoke your Lambda function locally using the AWS CLI or SDKs.
  Start a local endpoint that emulates the AWS Lambda service, and one can run their automated
  tests against this local Lambda endpoint. Invokes to this endpoint can be sent using the AWS CLI or
  SDK and they will in turn locally execute the Lambda function specified in the request.\n
"""


@click.command(
    "start-lambda",
    cls=InvokeLambdaCommand,
    help=HELP_TEXT,
    short_help=HELP_TEXT,
    description=DESCRIPTION,
    requires_credentials=False,
    context_settings={"max_content_width": 120},
)
@configuration_option(provider=ConfigProvider(section="parameters"))
@terraform_plan_file_option
@hook_name_click_option(
    force_prepare=False, invalid_coexist_options=["t", "template-file", "template", "parameter-overrides"]
)
@skip_prepare_infra_option
@service_common_options(3001)
@invoke_common_options
@warm_containers_common_options
@local_common_options
@cli_framework_options
@aws_creds_options
@save_params_option
@pass_context
@track_command
@check_newer_version
@print_cmdline_args
def cli(
    ctx,  # pylint: disable=R0914
    # start-lambda Specific Options
    host,
    port,
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
    save_params,
    config_file,
    config_env,
    warm_containers,
    shutdown,
    debug_function,
    container_host,
    container_host_interface,
    add_host,
    invoke_image,
    hook_name,
    skip_prepare_infra,
    terraform_plan_file,
):
    """
    `sam local start-lambda` command entry point
    """
    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing

    do_cli(
        ctx,
        host,
        port,
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
        hook_name,
    )  # pragma: no cover


def do_cli(  # pylint: disable=R0914
    ctx,
    host,
    port,
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
    hook_name,
):
    """
    Implementation of the ``cli`` method, just separated out for unit testing purposes
    """

    from samcli.commands.local.cli_common.invoke_context import InvokeContext
    from samcli.commands.local.cli_common.user_exceptions import UserException
    from samcli.commands.local.lib.exceptions import OverridesNotWellDefinedError
    from samcli.commands.local.lib.local_lambda_service import LocalLambdaService
    from samcli.commands.validate.lib.exceptions import InvalidSamDocumentException
    from samcli.lib.providers.exceptions import InvalidLayerReference
    from samcli.local.docker.lambda_debug_settings import DebuggingNotSupported

    LOG.debug("local start_lambda command is called")

    processed_invoke_images = process_image_options(invoke_image)

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
            container_host=container_host,
            container_host_interface=container_host_interface,
            add_host=add_host,
            invoke_images=processed_invoke_images,
        ) as invoke_context:
            service = LocalLambdaService(lambda_invoke_context=invoke_context, port=port, host=host)
            service.start()
            command_suggestions = generate_next_command_recommendation(
                [
                    ("Validate SAM template", "sam validate"),
                    ("Test Function in the Cloud", "sam sync --stack-name {{stack-name}} --watch"),
                    ("Deploy", "sam deploy --guided"),
                ]
            )
            click.secho(command_suggestions, fg="yellow")

    except (
        InvalidSamDocumentException,
        OverridesNotWellDefinedError,
        InvalidLayerReference,
        InvalidIntermediateImageError,
        DebuggingNotSupported,
        PortAlreadyInUse,
    ) as ex:
        raise UserException(str(ex), wrapped_from=ex.__class__.__name__) from ex
    except ContainerNotStartableException as ex:
        raise UserException(str(ex), wrapped_from=ex.__class__.__name__) from ex
    except ProcessSigTermException:
        LOG.debug("Successfully exited SIGTERM terminated process")
