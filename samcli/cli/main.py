"""
Entry point for the CLI
"""

import logging
import json
import click

from samcli import __version__
from .options import debug_option, region_option, profile_option
from .context import Context
from .command import BaseCommand

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')


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

    click.echo(json.dumps({
        "version": __version__
    }, indent=2))

    ctx.exit()


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
    pass
