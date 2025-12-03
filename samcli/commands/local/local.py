"""
Command group for "local" suite for commands. It provides common CLI arguments, template parsing capabilities,
setting up stdin/stdout etc
"""

import click

from samcli.cli.lazy_group import LazyGroup


@click.group(
    cls=LazyGroup,
    lazy_subcommands={
        "invoke": "samcli.commands.local.invoke.cli.cli",
        "start-api": "samcli.commands.local.start_api.cli.cli",
        "start-lambda": "samcli.commands.local.start_lambda.cli.cli",
        "generate-event": "samcli.commands.local.generate_event.cli.cli",
        "execution": "samcli.commands.local.execution.cli.cli",
        "callback": "samcli.commands.local.callback.cli.cli",
    },
)
def cli():
    """
    Run your Serverless application locally for quick development & testing
    """
