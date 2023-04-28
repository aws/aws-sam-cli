"""
Entry point for the CLI
"""

import json
import logging

import click

from samcli import __version__
from samcli.cli.command import BaseCommand
from samcli.cli.context import Context
from samcli.cli.global_config import GlobalConfig
from samcli.cli.options import debug_option, profile_option, region_option
from samcli.commands._utils.experimental import experimental, get_all_experimental_env_vars
from samcli.lib.utils.sam_logging import (
    LAMBDA_BULDERS_LOGGER_NAME,
    SAM_CLI_FORMATTER,
    SAM_CLI_LOGGER_NAME,
    SamCliLogger,
)
from samcli.lib.utils.system_info import gather_additional_dependencies_info, gather_system_info

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
    f = experimental(f)
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

    info = {
        "version": __version__,
        "system": gather_system_info(),
        "additional_dependencies": gather_additional_dependencies_info(),
        "available_beta_feature_env_vars": get_all_experimental_env_vars(),
    }
    click.echo(json.dumps(info, indent=2))

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
@click.option(
    "--info",
    is_flag=True,
    is_eager=True,
    callback=print_info,
    expose_value=False,
    help="Show system and dependencies information.",
)
@pass_context
def cli(ctx):
    """
    AWS Serverless Application Model (SAM) CLI

    The AWS Serverless Application Model Command Line Interface (AWS SAM CLI) is a command line tool
    that you can use with AWS SAM templates and supported third-party integrations to build and run
    your serverless applications.

    Learn more: https://docs.aws.amazon.com/serverless-application-model/
    """
    import atexit

    from samcli.lib.telemetry.metric import emit_all_metrics, send_installed_metric

    # if development version of SAM CLI is used, attach module proxy
    # to catch missing configuration for dynamic/hidden imports
    # TODO: in general, we need better mechanisms to set which execution environment is SAM CLI operating
    # rather than checking the executable name
    if ctx and getattr(ctx, "command_path", None) == "samdev":
        from samcli.cli.import_module_proxy import attach_import_module_proxy

        LOG.info("Attaching import module proxy for analyzing dynamic imports")
        attach_import_module_proxy()

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
