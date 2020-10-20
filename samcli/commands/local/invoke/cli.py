"""
CLI command for "local invoke" command
"""

import logging
import click

from samcli.cli.main import pass_context, common_options as cli_framework_options, aws_creds_options
from samcli.commands.local.cli_common.options import invoke_common_options
from samcli.lib.telemetry.metrics import track_command
from samcli.cli.cli_config_file import configuration_option, TomlProvider


LOG = logging.getLogger(__name__)

HELP_TEXT = """
You can use this command to execute your function in a Lambda-like environment locally.
You can pass in an event body using the -e (--event) parameter.
Logs from the Lambda function will be written to stdout.\n
\b
Invoking a Lambda function without an input event
$ sam local invoke "HelloWorldFunction"\n
\b
Invoking a Lambda function using an event file
$ sam local invoke "HelloWorldFunction" -e event.json\n
\b
Invoking a Lambda function using input from stdin
$ echo '{"message": "Hey, are you there?" }' | sam local invoke "HelloWorldFunction" --event - \n
"""
STDIN_FILE_NAME = "-"


@click.command("invoke", help=HELP_TEXT, short_help="Invokes a local Lambda function once.")
@configuration_option(provider=TomlProvider(section="parameters"))
@click.option(
    "--event",
    "-e",
    type=click.Path(),
    help="JSON file containing event data passed to the Lambda function during invoke. If this option "
    "is not specified, no event is assumed. Pass in the value '-' to input JSON via stdin",
)
@click.option("--no-event", is_flag=True, default=True, help="DEPRECATED: By default no event is assumed.", hidden=True)
@invoke_common_options
@cli_framework_options
@aws_creds_options
@click.argument("function_identifier", required=False)
@pass_context
@track_command  # pylint: disable=R0914
def cli(
    ctx,
    function_identifier,
    template_file,
    event,
    no_event,
    env_vars,
    debug_port,
    debug_args,
    debugger_path,
    docker_volume_basedir,
    docker_network,
    log_file,
    layer_cache_basedir,
    skip_pull_image,
    force_image_build,
    parameter_overrides,
    config_file,
    config_env,
):

    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing

    do_cli(
        ctx,
        function_identifier,
        template_file,
        event,
        no_event,
        env_vars,
        debug_port,
        debug_args,
        debugger_path,
        docker_volume_basedir,
        docker_network,
        log_file,
        layer_cache_basedir,
        skip_pull_image,
        force_image_build,
        parameter_overrides,
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
    docker_volume_basedir,
    docker_network,
    log_file,
    layer_cache_basedir,
    skip_pull_image,
    force_image_build,
    parameter_overrides,
):
    """
    Implementation of the ``cli`` method, just separated out for unit testing purposes
    """

    from samcli.commands.exceptions import UserException
    from samcli.lib.providers.exceptions import InvalidLayerReference
    from samcli.commands.local.cli_common.invoke_context import InvokeContext
    from samcli.local.lambdafn.exceptions import FunctionNotFound
    from samcli.commands.validate.lib.exceptions import InvalidSamDocumentException
    from samcli.commands.local.lib.exceptions import OverridesNotWellDefinedError, NoPrivilegeException
    from samcli.local.docker.manager import DockerImagePullFailedException
    from samcli.local.docker.lambda_debug_settings import DebuggingNotSupported

    LOG.debug("local invoke command is called")

    if event:
        event_data = _get_event(event)
    else:
        event_data = "{}"

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
            parameter_overrides=parameter_overrides,
            layer_cache_basedir=layer_cache_basedir,
            force_image_build=force_image_build,
            aws_region=ctx.region,
            aws_profile=ctx.profile,
        ) as context:

            # Invoke the function
            context.local_lambda_runner.invoke(
                context.function_name, event=event_data, stdout=context.stdout, stderr=context.stderr
            )

    except FunctionNotFound as ex:
        raise UserException(
            "Function {} not found in template".format(function_identifier), wrapped_from=ex.__class__.__name__
        ) from ex
    except (
        InvalidSamDocumentException,
        OverridesNotWellDefinedError,
        InvalidLayerReference,
        DebuggingNotSupported,
        NoPrivilegeException,
    ) as ex:
        raise UserException(str(ex), wrapped_from=ex.__class__.__name__) from ex
    except DockerImagePullFailedException as ex:
        raise UserException(str(ex), wrapped_from=ex.__class__.__name__) from ex


def _get_event(event_file_name):
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
    with click.open_file(event_file_name, "r") as fp:
        return fp.read()
