"""
CLI command for "delete" command
"""

import logging

import click
from samcli.cli.cli_config_file import TomlProvider, configuration_option
from samcli.cli.main import aws_creds_options, common_options, pass_context, print_cmdline_args

from samcli.lib.utils.version_checker import check_newer_version

SHORT_HELP = "Delete an AWS SAM application."

HELP_TEXT = """The sam delete command deletes a Cloudformation Stack and deletes all your resources which were created.

\b
e.g. sam delete --stack-name sam-app --region us-east-1

\b
"""

CONFIG_SECTION = "parameters"
CONFIG_COMMAND = "deploy"
LOG = logging.getLogger(__name__)


@click.command(
    "delete",
    short_help=SHORT_HELP,
    context_settings={"ignore_unknown_options": False, "allow_interspersed_args": True, "allow_extra_args": True},
    help=HELP_TEXT,
)
@configuration_option(provider=TomlProvider(section=CONFIG_SECTION, cmd_names=[CONFIG_COMMAND]))
@click.option(
    "--stack-name",
    required=False,
    help="The name of the AWS CloudFormation stack you want to delete. ",
)
@aws_creds_options
@common_options
@pass_context
@check_newer_version
@print_cmdline_args
def cli(
    ctx,
    stack_name,
    config_file,
    config_env,
):
    """
    `sam delete` command entry point
    """

    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing
    do_cli(stack_name, ctx.region, ctx.profile)  # pragma: no cover


def do_cli(stack_name, region, profile):
    """
    Implementation of the ``cli`` method
    """
    from samcli.commands.delete.delete_context import DeleteContext

    ctx = click.get_current_context()
    s3_bucket = ctx.default_map.get("s3_bucket", None)
    s3_prefix = ctx.default_map.get("s3_prefix", None)
    with DeleteContext(
        stack_name=stack_name,
        region=region,
        s3_bucket=s3_bucket,
        s3_prefix=s3_prefix,
        profile=profile
    ) as delete_context:
        delete_context.run()
