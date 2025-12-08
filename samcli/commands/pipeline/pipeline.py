"""
Command group for "pipeline" suite commands. It provides common CLI arguments, template parsing capabilities,
setting up stdin/stdout etc
"""

import click

from samcli.cli.lazy_group import LazyGroup


@click.group(
    cls=LazyGroup,
    lazy_subcommands={
        "bootstrap": "samcli.commands.pipeline.bootstrap.cli.cli",
        "init": "samcli.commands.pipeline.init.cli.cli",
    },
)
def cli() -> None:
    """
    Manage the continuous delivery of the application
    """
