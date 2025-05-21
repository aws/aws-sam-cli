"""
CLI command for "delete" command
"""

import logging
from typing import Optional

import click

from samcli.cli.cli_config_file import ConfigProvider, configuration_option, save_params_option
from samcli.cli.main import aws_creds_options, common_options, pass_context, print_cmdline_args
from samcli.commands._utils.command_exception_handler import command_exception_handler
from samcli.commands.delete.delete_context import CONFIG_COMMAND, CONFIG_SECTION
from samcli.lib.telemetry.metric import track_command
from samcli.lib.utils.version_checker import check_newer_version

SHORT_HELP = "Delete an AWS SAM application and the artifacts created by sam deploy."

HELP_TEXT = """The sam delete command deletes the CloudFormation
stack and all the artifacts which were created using sam deploy.
"""

LOG = logging.getLogger(__name__)


@click.command(
    "delete",
    short_help=SHORT_HELP,
    context_settings={"ignore_unknown_options": False, "allow_interspersed_args": True, "allow_extra_args": True},
    help=HELP_TEXT,
)
@configuration_option(provider=ConfigProvider(CONFIG_SECTION, [CONFIG_COMMAND]))
@click.option(
    "--stack-name",
    required=False,
    help="The name of the AWS CloudFormation stack you want to delete. ",
)
@click.option(
    "--no-prompts",
    help=("Specify this flag to allow SAM CLI to skip through the guided prompts."),
    is_flag=True,
    required=False,
)
@click.option(
    "--s3-bucket",
    help=("The S3 bucket path you want to delete."),
    type=click.STRING,
    default=None,
    required=False,
)
@click.option(
    "--s3-prefix",
    help=("The S3 prefix you want to delete"),
    type=click.STRING,
    default=None,
    required=False,
)
@aws_creds_options
@common_options
@save_params_option
@pass_context
@track_command
@check_newer_version
@print_cmdline_args
@command_exception_handler
def cli(
    ctx,
    stack_name: str,
    no_prompts: bool,
    s3_bucket: str,
    s3_prefix: str,
    config_env: str,
    config_file: str,
    save_params: bool,
):
    """
    `sam delete` command entry point
    """

    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing
    do_cli(
        stack_name=stack_name,
        region=ctx.region,
        profile=ctx.profile,
        no_prompts=no_prompts,
        s3_bucket=s3_bucket,
        s3_prefix=s3_prefix,
    )  # pragma: no cover


def do_cli(
    stack_name: str,
    region: str,
    profile: str,
    no_prompts: bool,
    s3_bucket: Optional[str],
    s3_prefix: Optional[str],
):
    """
    Implementation of the ``cli`` method
    """
    from samcli.commands.delete.delete_context import DeleteContext

    with DeleteContext(
        stack_name=stack_name,
        region=region,
        profile=profile,
        no_prompts=no_prompts,
        s3_bucket=s3_bucket,
        s3_prefix=s3_prefix,
    ) as delete_context:
        delete_context.run()
