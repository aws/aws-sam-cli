"""
Sets up the cli for stack-outputs
"""

import click

from samcli.cli.main import pass_context

HELP_TEXT = """
Get the stack outputs as defined in the SAM/CloudFormation template.
"""

# @click.command(name="resources", cls=GenerateEventCommand, help=HELP_TEXT)


@click.command(name="stack-outputs", help=HELP_TEXT)
@click.option(
    "--stack-name",
    help=("Name of corresponding deployed stack."),
    required=True,
    type=click.STRING,
)
@click.option(
    "--output",
    help=("Output the results from the command in a given" "output format (json, yaml, table or text)."),
    type=click.Choice(["json", "yaml", "table", "text"], case_sensitive=False),
)
@pass_context
def cli(self, stack_name, output):
    """
    Generate an event for one of the services listed below:
    """
