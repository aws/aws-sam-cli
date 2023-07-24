"""
CLI command for "local invoke" command
"""

import logging

import click

from samcli.cli.cli_config_file import ConfigProvider, configuration_option
from samcli.cli.main import aws_creds_options, pass_context, print_cmdline_args
from samcli.cli.main import common_options as cli_framework_options
from samcli.commands._utils.experimental import ExperimentalFlag, is_experimental_enabled
from samcli.commands._utils.option_value_processor import process_image_options
from samcli.commands._utils.options import hook_name_click_option, skip_prepare_infra_option
from samcli.commands.local.cli_common.options import invoke_common_options, local_common_options
from samcli.commands.local.invoke.core.command import InvokeCommand
from samcli.commands.local.lib.exceptions import InvalidIntermediateImageError
from samcli.lib.telemetry.metric import track_command
from samcli.lib.utils.version_checker import check_newer_version
from samcli.local.docker.exceptions import ContainerNotStartableException, PortAlreadyInUse

LOG = logging.getLogger(__name__)

HELP_TEXT = """
    Invoke AWS serverless functions locally.
"""

DESCRIPTION = """
  Invoke lambda functions in a Lambda-like environment locally.
  An event body can be passed using the -e (--event) parameter.
  Logs from the Lambda function will be written to stdout.
"""

STDIN_FILE_NAME = "-"


@click.command(
    "invoke",
    cls=InvokeCommand,
    help=HELP_TEXT,
    description=DESCRIPTION,
    requires_credentials=False,
    short_help=HELP_TEXT,
    context_settings={"max_content_width": 120},
)
@configuration_option(provider=ConfigProvider(section="parameters"))
@hook_name_click_option(
    force_prepare=False, invalid_coexist_options=["t", "template-file", "template", "parameter-overrides"]
)
@skip_prepare_infra_option
@click.option(
    "--event",
    "-e",
    type=click.Path(),
    help="JSON file containing event data passed to the Lambda function during invoke. If this option "
    "is not specified, no event is assumed. Pass in the value '-' to input JSON via stdin",
)
@click.option("--no-event", is_flag=True, default=True, help="DEPRECATED: By default no event is assumed.", hidden=True)
@invoke_common_options
@local_common_options
@cli_framework_options
@aws_creds_options
@click.argument("function_logical_id", required=False)
@pass_context
@track_command  # pylint: disable=R0914
@check_newer_version
@print_cmdline_args
def cli(
    ctx,
    function_logical_id,
    template_file,
    event,
    no_event,
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
    shutdown,
    parameter_overrides,
    config_file,
    config_env,
    container_host,
    container_host_interface,
    invoke_image,
    hook_name,
    skip_prepare_infra,
):
    """
    `sam local invoke` command entry point
    """
    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing

    do_cli(
        ctx,
        function_logical_id,
        template_file,
        event,
        no_event,
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
        shutdown,
        parameter_overrides,
        container_host,
        container_host_interface,
        invoke_image,
        hook_name,
    )  # pragma: no cover


def do_cli(  # pylint: disable=R0914
    ctx,
    function_identifier,
    template,
    event,
    no_event,
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
    shutdown,
    parameter_overrides,
    container_host,
    container_host_interface,
    invoke_image,
    hook_name,
):
    """
    Implementation of the ``cli`` method, just separated out for unit testing purposes
    """

    from samcli.commands.exceptions import UserException
    from samcli.commands.local.cli_common.invoke_context import InvokeContext
    from samcli.commands.local.lib.exceptions import NoPrivilegeException, OverridesNotWellDefinedError
    from samcli.commands.validate.lib.exceptions import InvalidSamDocumentException
    from samcli.lib.providers.exceptions import InvalidLayerReference
    from samcli.local.docker.lambda_debug_settings import DebuggingNotSupported
    from samcli.local.docker.manager import DockerImagePullFailedException
    from samcli.local.lambdafn.exceptions import FunctionNotFound

    if (
        hook_name
        and ExperimentalFlag.IaCsSupport.get(hook_name) is not None
        and not is_experimental_enabled(ExperimentalFlag.IaCsSupport.get(hook_name))
    ):
        LOG.info("Terraform Support beta feature is not enabled.")
        return

    LOG.debug("local invoke command is called")

    if event:
        event_data = _get_event(event, exception_class=UserException)
    else:
        event_data = "{}"

    processed_invoke_images = process_image_options(invoke_image)

    # Pass all inputs to setup necessary context to invoke function locally.
    # Handler exception raised by the processor for invalid args and print errors
    try:
        with InvokeContext(
            template_file=template,
            function_identifier=function_identifier,
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
            shutdown=shutdown,
            container_host=container_host,
            container_host_interface=container_host_interface,
            invoke_images=processed_invoke_images,
        ) as context:
            # Invoke the function
            context.local_lambda_runner.invoke(
                context.function_identifier, event=event_data, stdout=context.stdout, stderr=context.stderr
            )

    except FunctionNotFound as ex:
        raise UserException(
            "Function {} not found in template".format(function_identifier), wrapped_from=ex.__class__.__name__
        ) from ex
    except (
        InvalidSamDocumentException,
        OverridesNotWellDefinedError,
        InvalidLayerReference,
        InvalidIntermediateImageError,
        DebuggingNotSupported,
        NoPrivilegeException,
        PortAlreadyInUse,
    ) as ex:
        raise UserException(str(ex), wrapped_from=ex.__class__.__name__) from ex
    except DockerImagePullFailedException as ex:
        raise UserException(str(ex), wrapped_from=ex.__class__.__name__) from ex
    except ContainerNotStartableException as ex:
        raise UserException(str(ex), wrapped_from=ex.__class__.__name__) from ex


def _get_event(event_file_name, exception_class):
    """
    Read the event JSON data from the given file. If no file is provided, read the event from stdin.

    :param string event_file_name: Path to event file, or '-' for stdin
    :return string: Contents of the event file or stdin
    """

    if event_file_name == STDIN_FILE_NAME:
        # If event is empty, listen to stdin for event data until EOF
        LOG.info("Reading invoke payload from stdin (you can also pass it from file with --event)")

    # click.open_file knows to open stdin when filename is '-'. This is safer than manually opening streams, and
    # accidentally closing a standard stream
    try:
        with click.open_file(event_file_name, "r", encoding="utf-8") as fp:
            return fp.read()
    except FileNotFoundError as ex:
        raise exception_class(str(ex), wrapped_from=ex.__class__.__name__) from ex
