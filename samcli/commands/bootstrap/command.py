"""
CLI command for "bootstrap", which sets up a SAM development environment
"""
import click

from samcli.cli.main import aws_creds_options, common_options, pass_context
from samcli.lib.bootstrap import bootstrap
from samcli.lib.telemetry.metric import track_command
from samcli.lib.utils.version_checker import check_newer_version

SHORT_HELP = "Set up development environment for AWS SAM applications."

HELP_TEXT = """
Sets up a development environment for AWS SAM applications.

Currently this creates, if one does not exist, a managed S3 bucket for your account in your working AWS region.
"""


@click.command("bootstrap", short_help=SHORT_HELP, help=HELP_TEXT, context_settings=dict(max_content_width=120))
@common_options
@aws_creds_options
@pass_context
@track_command
@check_newer_version
def cli(ctx):
    do_cli(ctx.region, ctx.profile)  # pragma: no cover


def do_cli(region, profile):  # pragma: no cover
    bucket_name = bootstrap.manage_stack(profile=profile, region=region)
    click.echo("Source Bucket: " + bucket_name)
