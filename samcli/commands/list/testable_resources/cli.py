"""
Sets up the cli for resources
"""

import click

from samcli.commands.list.cli_common.options import stack_name_option, output_option
from samcli.cli.main import pass_context, common_options, aws_creds_options, print_cmdline_args
from samcli.lib.utils.version_checker import check_newer_version
from samcli.lib.telemetry.metric import track_command
from samcli.commands._utils.options import template_option_without_build
from samcli.cli.cli_config_file import configuration_option, TomlProvider


HELP_TEXT = """
Get a summary of the testable resources in the stack.\n
This command will show both the cloud and local endpoints that can
be used with sam local and sam sync. Currently the testable resources
are lambda functions and API Gateway API resources.
"""


@click.command(name="testable-resources", help=HELP_TEXT)
@configuration_option(provider=TomlProvider(section="parameters"))
@stack_name_option
@output_option
@template_option_without_build
@aws_creds_options
@common_options
@pass_context
@track_command
@check_newer_version
@print_cmdline_args
def cli(self, stack_name, output, template_file, config_file, config_env):
    """
    `sam list testable-resources` command entry point
    """
    do_cli(stack_name=stack_name, output=output, region=self.region, profile=self.profile, template_file=template_file)


def do_cli(stack_name, output, region, profile, template_file):
    """
    Implementation of the ``cli`` method
    """
    from samcli.commands.list.testable_resources.testable_resources_context import TestableResourcesContext

    with TestableResourcesContext(
        stack_name=stack_name, output=output, region=region, profile=profile, template_file=template_file
    ) as testable_resources_context:
        testable_resources_context.run()
