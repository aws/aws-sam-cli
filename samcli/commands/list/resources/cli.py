"""
Sets up the cli for resources
"""

import click

from samcli.cli.main import pass_context

HELP_TEXT = """
Get a list of resources that will be deployed to CloudFormation.\n

If a stack name is provided, the corresponding physical IDs of each
resource will be mapped to the logical ID of each resource.
"""

# @click.command(name="resources", cls=GenerateEventCommand, help=HELP_TEXT)


@click.command(name="resources", help=HELP_TEXT)
@click.option(
    "--stack-name",
    help=(
        "Name of corresponding deployed stack.(Not including"
        "a stack name will only show local resources defined"
        "in the template.)"
    ),
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

    do_cli(stack_name, output)


def do_cli(stack_name, output):
    pass
