"""
CLI command for "deploy" command
"""
import os

import logging
import functools

import click

from samcli.cli.main import pass_context, common_options as cli_framework_options, aws_creds_options, print_cmdline_args
from samcli.cli.cli_config_file import TomlProvider, configuration_option
from samcli.lib.telemetry.metric import track_command
from samcli.lib.utils.version_checker import check_newer_version
from samcli.commands._utils.options import template_option_without_build

from samtranslator.translator.translator import Translator
from samtranslator.public.exceptions import InvalidDocumentException
from .exceptions import InvalidSamDocumentException

import boto3
from samtranslator.translator.managed_policy_translator import ManagedPolicyLoader
from samtranslator.parser import parser
from boto3.session import Session
from samcli.yamlhelper import yaml_dump
from samcli.lib.utils.packagetype import ZIP

from samcli.lib.replace_uri.replace_uri import ReplaceLocalCodeUri



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
# options go here with this format
# @click.option(
#     "--test",
#     "-t",
#     required=False,
#     is_flag=True,
#     help="Test number 1",
# )
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
    `sam deploy` command entry point
    """
    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing
    do_cli(ctx, template_file)  # pragma: no cover


def do_cli(ctx, template):
    """
    Implementation of the ``cli`` method

    Translate template into CloudFormation yaml format
    """

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
