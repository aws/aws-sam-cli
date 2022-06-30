"""
Entry point for the CLI
"""

import logging
import json
import atexit
import click

from samcli import __version__
from samcli.lib.telemetry.metric import send_installed_metric, emit_all_metrics
from samcli.lib.utils.sam_logging import (
    LAMBDA_BULDERS_LOGGER_NAME,
    SamCliLogger,
    SAM_CLI_FORMATTER,
    SAM_CLI_LOGGER_NAME,
)
from .options import debug_option, region_option, profile_option
from .context import Context
from .command import BaseCommand
from .global_config import GlobalConfig

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")


pass_context = click.make_pass_decorator(Context)


def common_options(f):
    """
    Common CLI options used by all commands. Ex: --debug
    :param f: Callback function passed by Click
    :return: Callback function
    """
    f = debug_option(f)
    return f


def aws_creds_options(f):
    """
    Common CLI options necessary to interact with AWS services
    """
    f = region_option(f)
    f = profile_option(f)
    return f


def print_info(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return

    click.echo(json.dumps({"version": __version__}, indent=2))

    ctx.exit()


def print_cmdline_args(func):
    """
    This function format and print out the command line arguments for debugging.

    Parameters
    ----------
    func: Callable
        Actual function (command) which will be executed

    Returns
    -------
    function reference:
        A wrapped function reference which executes original function and checks newer version of SAM CLI
    """

    def wrapper(*args, **kwargs):
        if kwargs.get("config_file") and kwargs.get("config_env"):
            config_file = kwargs["config_file"]
            config_env = kwargs["config_env"]
            LOG.debug("Using config file: %s, config environment: %s", config_file, config_env)
        LOG.debug("Expand command line arguments to:")
        cmdline_args_log = ""
        for key, value in kwargs.items():
            if key not in ["config_file", "config_env"]:
                if isinstance(value, bool) and value:
                    cmdline_args_log += f"--{key} "
                elif value:
                    cmdline_args_log += f"--{key}={str(value)} "
        LOG.debug(cmdline_args_log)
        return func(*args, **kwargs)

    return wrapper


# Keep the message to 80chars wide to it prints well on most terminals
TELEMETRY_PROMPT = """
\tSAM CLI now collects telemetry to better understand customer needs.

\tYou can OPT OUT and disable telemetry collection by setting the
\tenvironment variable SAM_CLI_TELEMETRY=0 in your shell.
\tThanks for your help!

\tLearn More: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-telemetry.html
"""  # noqa


@click.command(cls=BaseCommand)
@common_options
@click.version_option(version=__version__, prog_name="SAM CLI")
@click.option("--info", is_flag=True, is_eager=True, callback=print_info, expose_value=False)
@pass_context
def cli(ctx):
    """
    AWS Serverless Application Model (SAM) CLI

    The AWS Serverless Application Model extends AWS CloudFormation to provide a simplified way of defining the
    Amazon API Gateway APIs, AWS Lambda functions, and Amazon DynamoDB tables needed by your serverless application.
    You can find more in-depth guide about the SAM specification here:
    https://github.com/awslabs/serverless-application-model.
    """
    gc = GlobalConfig()
    if gc.telemetry_enabled is None:
        enabled = True

        try:
            gc.telemetry_enabled = enabled

            if enabled:
                click.secho(TELEMETRY_PROMPT, fg="yellow", err=True)

                # When the Telemetry prompt is printed, we can safely assume that this is the first time someone
                # is installing SAM CLI on this computer. So go ahead and send the `installed` metric
                send_installed_metric()

        except (IOError, ValueError) as ex:
            LOG.debug("Unable to write telemetry flag", exc_info=ex)

    sam_cli_logger = logging.getLogger(SAM_CLI_LOGGER_NAME)
    lambda_builders_logger = logging.getLogger(LAMBDA_BULDERS_LOGGER_NAME)
    botocore_logger = logging.getLogger("botocore")

    atexit.register(emit_all_metrics)

    SamCliLogger.configure_logger(sam_cli_logger, SAM_CLI_FORMATTER, logging.INFO)
    SamCliLogger.configure_logger(lambda_builders_logger, SAM_CLI_FORMATTER, logging.INFO)
    SamCliLogger.configure_null_logger(botocore_logger)
