"""
CLI command for "deploy" command
"""
import os
import ast
from samtranslator.model import sam_resources
import yaml

import logging
import functools
from samcli.commands.check.pricing_calculations import PricingCalculations

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
from samcli.commands.check.resources.lambda_function import LambdaFunction

from samcli.commands.check.resources.pricing import Pricing
from .exceptions import InvalidSamDocumentException

from .bottle_neck_calculations import BottleNeckCalculations
from .print_results import PrintResults

from samcli.commands.check.lib.resource_provider import ResourceProvider

from samcli.commands.check.lib.save_data import SaveGraphData

from samcli.commands.check.lib.load_data import LoadData


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

CONFIG_SECTION = "parameters"
LOG = logging.getLogger(__name__)


@click.command(
    "check",
    short_help=SHORT_HELP,
    help=HELP_TEXT,
)
@configuration_option(provider=TomlProvider(section="parameters"))
@template_option_without_build
@click.option(
    "--load",
    required=False,
    is_flag=True,
    help="Load data in the config file",
)
@aws_creds_options
@cli_framework_options
@pass_context
@track_command
@check_newer_version
@print_cmdline_args
def cli(ctx, template_file, config_file, config_env, load):
    """
    `sam deploy` command entry point
    """
    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing
    do_cli(ctx, template_file, config_file, load)  # pragma: no cover


def do_cli(ctx, template, config_file, load):
    """
    Implementation of the ``cli`` method

    Translate template into CloudFormation yaml format
    """

    if load:
        load_data = LoadData()
        graph = load_data.generate_graph_from_toml(config_file)

        bottle_neck_calculations = BottleNeckCalculations(graph)
        bottle_neck_calculations.run_calculations()

        pricing_calculations = PricingCalculations(graph)
        pricing_calculations.run_calculations()

        save_data = False

        if save_data:
            save_graph_data = SaveGraphData(graph)
            save_graph_data.save_to_config_file(config_file)

        results = PrintResults(graph, pricing_calculations.get_lambda_pricing_results())
        results.print_all_pricing_results()
        results.print_bottle_neck_results()

        return

    # acquire template and policies
    sam_template = _read_sam_file(template)
    iam_client = boto3.client("iam")
    managed_policy_map = ManagedPolicyLoader(iam_client).load()

    sam_translator = Translator(
        managed_policy_map=managed_policy_map,
        sam_parser=parser.Parser(),
        plugins=[],
        boto_session=Session(profile_name=ctx.profile, region_name=ctx.region),
    )

    # Convert uri's
    uri_replace = ReplaceLocalCodeUri(sam_template)
    sam_template = uri_replace._replace_local_codeuri()

    # Translate template
    try:
        template = sam_translator.translate(sam_template=sam_template, parameter_values={})
    except InvalidDocumentException as e:
        raise InvalidSamDocumentException(
            functools.reduce(lambda message, error: message + " " + str(error), e.causes, str(e))
        ) from e

    click.echo("... analyzing application template")

    graph = parse_template(template)

    bottle_necks = BottleNecks(graph)
    bottle_necks.ask_entry_point_question()

    bottle_neck_calculations = BottleNeckCalculations(graph)
    bottle_neck_calculations.run_calculations()

    pricing_calculations = PricingCalculations(graph)
    pricing_calculations.run_calculations()

    save_data = ask_to_save_data()

    if save_data:
        save_graph_data = SaveGraphData(graph)
        save_graph_data.save_to_config_file(config_file)

    results = PrintResults(graph, pricing_calculations.get_lambda_pricing_results())
    results.print_all_pricing_results()
    results.print_bottle_neck_results()


def ask_to_save_data():
    correct_input = False
    while not correct_input:
        user_input = click.prompt("Would you like to save this data in the samconfig file for future use? [y/n]")
        user_input = user_input.lower()

        if user_input == "y":
            return True
        elif user_input == "n":
            return False
        else:
            click.echo("Please enter a valid responce.")


def parse_template(template):

    all_resources = {}

    resource_provider = ResourceProvider(template)
    all_resources = resource_provider.get_all_resources()

    # After all resources have been parsed from template, pass them into the graph
    graph_context = GraphContext(all_resources)

    return graph_context.generate()


def _read_sam_file(template):
    """
    Reads the file (json and yaml supported) provided and returns the dictionary representation of the file.

    :param str template: Path to the template file
    :return dict: Dictionary representing the SAM Template
    :raises: SamTemplateNotFoundException when the template file does not exist
    """

    from samcli.commands.local.cli_common.user_exceptions import SamTemplateNotFoundException
    from samcli.yamlhelper import yaml_parse

    if not os.path.exists(template):
        click.secho("SAM Template Not Found", bg="red")
        raise SamTemplateNotFoundException("Template at {} is not found".format(template))

    with click.open_file(template, "r", encoding="utf-8") as sam_template:
        sam_template = yaml_parse(sam_template.read())

    return sam_template
