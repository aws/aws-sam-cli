"""
Generates an Api Gateway Event for a Lambda Invoke
"""
import json

import click

from samcli.cli.main import pass_context, common_options as cli_framework_options
from samcli.commands.local.lib.events import generate_api_event


@click.command("api", short_help="Generates a sample Amazon API Gateway event")
@click.option("--method", "-m",
              type=str,
              default="POST",
              help='HTTP method (default: "POST")')
@click.option("--body", "-b",
              type=str,
              default="{ \"test\": \"body\"}",
              help='HTTP body (default: "{ \"test\": \"body\"}")')
@click.option("--resource", "-r",
              type=str,
              default="/{proxy+}",
              help='API Gateway resource name (default: "/{proxy+}")')
@click.option("--path", "-p",
              type=str,
              default="/examplepath",
              help=' HTTP path (default: "/examplepath")')
@cli_framework_options
@pass_context
def cli(ctx, method, body, resource, path):
    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing

    do_cli(ctx, method, body, resource, path)  # pragma: no cover


def do_cli(ctx, method, body, resource, path):
    """
    Implementation of the ``cli`` method, just separated out for unit testing purposes
    """
    event_dict = generate_api_event(method, body, resource, path)
    event = json.dumps(event_dict, indent=4)
    click.echo(event)
