"""
CLI command for "package" command
"""

from functools import partial
import click

from samcli.cli.main import pass_context, common_options
from samcli.commands._utils.options import get_or_default_template_file_name, _TEMPLATE_OPTION_DEFAULT_VALUE
from samcli.lib.samlib.cloudformation_command import execute_command
from samcli.commands.exceptions import UserException


SHORT_HELP = "Package an AWS SAM application. This is an alias for 'aws cloudformation package'."


HELP_TEXT = """The SAM package command creates a zip of your code and dependencies and uploads it to S3. The command
returns a copy of your template, replacing references to local artifacts with the S3 location where the command
uploaded the artifacts.

\b
e.g. sam package --template-file template.yaml  --output-template-file packaged.yaml
--s3-bucket REPLACE_THIS_WITH_YOUR_S3_BUCKET_NAME

\b
This is an alias for aws cloudformation package. To learn about other parameters you can use,
run aws cloudformation package help.
"""


@click.command("package", short_help=SHORT_HELP, context_settings={"ignore_unknown_options": True}, help=HELP_TEXT)
@click.option('--template-file',
              default=_TEMPLATE_OPTION_DEFAULT_VALUE,
              type=click.Path(),
              callback=partial(get_or_default_template_file_name, include_build=True),
              show_default=False,
              help="The path where your AWS SAM template is located")
@click.option('--s3-bucket',
              required=True,
              help="The name of the S3 bucket where this command uploads the artifacts that "
                   "are referenced in your template.")
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
@common_options
@pass_context
def cli(ctx, args, template_file, s3_bucket):

    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing

    do_cli(args, template_file, s3_bucket)  # pragma: no cover


def do_cli(args, template_file, s3_bucket):
    args = args + ('--s3-bucket', s3_bucket)

    try:
        execute_command("package", args, template_file)
    except OSError as ex:
        raise UserException(str(ex))
