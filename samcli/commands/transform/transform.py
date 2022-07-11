"""
CLI Command for Creating a MOCK SAM Template
"""
import boto3
import click

from samcli.cli.main import pass_context, common_options as cli_framework_options, print_cmdline_args
from samcli.commands._utils.cdk_support_decorators import unsupported_command_cdk
from samcli.commands._utils.options import template_option_without_build
from samcli.lib.telemetry.metric import track_command
from samcli.cli.cli_config_file import configuration_option, TomlProvider
from samcli.lib.utils.version_checker import check_newer_version
from samcli.commands.validate.validate import _read_sam_file

@click.command("transform", short_help="Outputs transformed template")
@configuration_option(provider=TomlProvider(section="parameters"))
@template_option_without_build
@cli_framework_options
@pass_context
@track_command
@check_newer_version
@print_cmdline_args
@unsupported_command_cdk(alternative_command="cdk doctor")
def cli(
    ctx,
    template_file,
    config_file,
    config_env,
):

    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing

    do_cli(ctx, template_file)  # pragma: no cover

def do_cli(ctx, template):
    """
    Implementation of the ``cli`` method, just separated out for unit testing purposes
    """
    from samtranslator.translator.managed_policy_translator import ManagedPolicyLoader
    from samcli.commands.local.cli_common.user_exceptions import InvalidSamTemplateException
    from samcli.commands.validate.lib.exceptions import InvalidSamDocumentException
    from samcli.commands.validate.lib.sam_template_validator import SamTemplateValidator

    sam_template = _read_sam_file(template)

    iam_client = boto3.client("iam")

    transformer = SamTemplateValidator(
        sam_template, ManagedPolicyLoader(iam_client), profile=ctx.profile,  region='us-east-1'
    )

    """
    Purpose of this command is to output the transformed template, even if the user is not logged
    into their AWS account. Changes to the validate method have been added to use the functionality
    of the command `sam validate -template {template_name} --debug` which when called will return
    the transformed template with several other reports. This command will ONLY output the template.
    """

    try:
        click.echo(transformer.create_template())
    except InvalidSamDocumentException as e:
        click.secho("Template provided at '{}' was invalid SAM Template.\n".format(template), bg="red")
        raise InvalidSamTemplateException(str(e)) from e
