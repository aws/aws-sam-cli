"""
CLI command for "local start-lambda" command
"""

import logging
import click

from samcli.cli.main import pass_context, common_options as cli_framework_options, aws_creds_options
from samcli.commands.local.cli_common.options import invoke_common_options, service_common_options
from samcli.lib.telemetry.metrics import track_command
from samcli.cli.cli_config_file import configuration_option, TomlProvider


LOG = logging.getLogger(__name__)

HELP_TEXT = """
You can use this command to programmatically invoke your Lambda function locally using the AWS CLI or SDKs.
This command starts a local endpoint that emulates the AWS Lambda service, and you can run your automated
tests against this local Lambda endpoint. When you send an invoke to this endpoint using the AWS CLI or
SDK, it will locally execute the Lambda function specified in the request.\n
\b
SETUP
------
Start the local Lambda endpoint by running this command in the directory that contains your AWS SAM template.
$ sam local start-lambda\n
\b
USING AWS CLI
-------------
Then, you can invoke your Lambda function locally using the AWS CLI
$ aws lambda invoke --function-name "HelloWorldFunction" --endpoint-url "http://127.0.0.1:3001" --no-verify-ssl out.txt
\n
\b
USING AWS SDK
-------------
You can also use the AWS SDK in your automated tests to invoke your functions programatically.
Here is a Python example:
    self.lambda_client = boto3.client('lambda',
                                  endpoint_url="http://127.0.0.1:3001",
                                  use_ssl=False,
                                  verify=False,
                                  config=Config(signature_version=UNSIGNED,
                                                read_timeout=0,
                                                retries={'max_attempts': 0}))
    self.lambda_client.invoke(FunctionName="HelloWorldFunction")
"""


@click.command(
    "start-lambda",
    help=HELP_TEXT,
    short_help="Starts a local endpoint you can use to invoke your local Lambda functions.",
)
@configuration_option(provider=TomlProvider(section="parameters"))
@service_common_options(3001)
@invoke_common_options
@cli_framework_options
@aws_creds_options
@pass_context
@track_command
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
    docker_volume_basedir,
    docker_network,
    log_file,
    layer_cache_basedir,
    skip_pull_image,
    force_image_build,
    parameter_overrides,
    config_file,
    config_env,
):  # pylint: disable=R0914
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
    host,
    port,
    template,
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

    from samcli.commands.local.cli_common.invoke_context import InvokeContext
    from samcli.commands.local.cli_common.user_exceptions import UserException
    from samcli.lib.providers.exceptions import InvalidLayerReference
    from samcli.commands.local.lib.local_lambda_service import LocalLambdaService
    from samcli.commands.validate.lib.exceptions import InvalidSamDocumentException
    from samcli.commands.local.lib.exceptions import OverridesNotWellDefinedError
    from samcli.local.docker.lambda_debug_settings import DebuggingNotSupported

    LOG.debug("local start_lambda command is called")

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
            parameter_overrides=parameter_overrides,
            layer_cache_basedir=layer_cache_basedir,
            force_image_build=force_image_build,
            aws_region=ctx.region,
            aws_profile=ctx.profile,
        ) as invoke_context:

            service = LocalLambdaService(lambda_invoke_context=invoke_context, port=port, host=host)
            service.start()

    except (
        InvalidSamDocumentException,
        OverridesNotWellDefinedError,
        InvalidLayerReference,
        DebuggingNotSupported,
    ) as ex:
        raise UserException(str(ex), wrapped_from=ex.__class__.__name__) from ex
