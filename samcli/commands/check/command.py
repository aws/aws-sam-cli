"""
CLI command for "check" command
"""

import logging

import click

from samcli.cli.main import pass_context, common_options as cli_framework_options, aws_creds_options, print_cmdline_args
from samcli.cli.cli_config_file import TomlProvider, configuration_option
from samcli.lib.telemetry.metric import track_command
from samcli.lib.utils.version_checker import check_newer_version
from samcli.commands._utils.options import template_option_without_build


from samtranslator.translator.translator import Translator
from samtranslator.public.exceptions import InvalidDocumentException

import boto3
from samtranslator.translator.managed_policy_translator import ManagedPolicyLoader
from samtranslator.parser import parser
from boto3.session import Session
from samcli.yamlhelper import yaml_dump
from samcli.lib.utils.packagetype import ZIP

from samcli.lib.replace_uri.replace_uri import ReplaceLocalCodeUri

from samcli.lib.providers.sam_function_provider import SamFunctionProvider
from samcli.lib.providers.sam_stack_provider import SamLocalStackProvider
from .bottle_necks import BottleNecks
from .graph_context import GraphContext
from .resources.LambdaFunction import LambdaFunction

from .resources.Pricing import Pricing
from .exceptions import InvalidSamDocumentException

from .calculations import Calculations
from .print_results import PrintResults



SHORT_HELP = "Checks template for bottle necks."


HELP_TEXT = """
Check your application to determine if any endpoints will not be able to
provide the expected arival rate of data. You will need to provide the
expected duration of each lambda function, as well as the expected 
per-second arrival rate. You will then be informed of the expected cost
of running this application, as well as any bottle necks that may exist.

This command must be run in the main directory of your application. 
This command will work on any SAM application. It can also run 
on a CloudFormation template.

Connections between resources can be made after all required data is
provided
"""

LOG = logging.getLogger(__name__)


@click.command(
    "check",
    short_help=SHORT_HELP,
    help=HELP_TEXT,
)
@configuration_option(provider=TomlProvider(section="parameters"))
@template_option_without_build
@aws_creds_options
@cli_framework_options
@pass_context
@track_command
@check_newer_version
@print_cmdline_args
def cli(
    ctx,
    template_file,
    config_file,
    config_env,
):
    """
    `sam check` command entry point
    """
    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing
    do_cli(ctx, template_file)  # pragma: no cover


def do_cli(ctx, template_path):
    """
    Implementation of the ``cli`` method
    """

    from samcli.commands.check.lib.command_context import CheckContext

    pricing = Pricing(graph)
    pricing.ask_pricing_questions()

    click.echo("Running calculations...")

    calculations = Calculations(graph)
    calculations.run_bottle_neck_calculations()

    results = PrintResults(graph)
    results.print_bottle_neck_results()



    context = CheckContext(ctx.region, ctx.profile, template_path)
    context.run()
