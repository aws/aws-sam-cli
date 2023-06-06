"""
Sets up the cli for resources
"""

import click

from samcli.cli.cli_config_file import ConfigProvider, configuration_option
from samcli.cli.main import aws_creds_options, common_options, pass_context, print_cmdline_args
from samcli.commands._utils.command_exception_handler import command_exception_handler
from samcli.commands._utils.options import parameter_override_option, template_option_without_build
from samcli.commands.list.cli_common.options import output_option, stack_name_not_provided_message, stack_name_option
from samcli.lib.telemetry.metric import track_command
from samcli.lib.utils.version_checker import check_newer_version

HELP_TEXT = """
Get a summary of the cloud endpoints in the stack.\n
This command will show both the cloud and local endpoints that can
be used with sam local and sam sync. Currently the endpoint resources
are Lambda functions and API Gateway API resources.
"""


@click.command(name="endpoints", help=HELP_TEXT)
@configuration_option(provider=ConfigProvider(section="parameters"))
@parameter_override_option
@stack_name_option
@output_option
@template_option_without_build
@aws_creds_options
@common_options
@pass_context
@track_command
@check_newer_version
@print_cmdline_args
@command_exception_handler
def cli(self, parameter_overrides, stack_name, output, template_file, config_file, config_env):
    """
    `sam list endpoints` command entry point
    """
    do_cli(
        parameter_overrides=parameter_overrides,
        stack_name=stack_name,
        output=output,
        region=self.region,
        profile=self.profile,
        template_file=template_file,
    )


def do_cli(parameter_overrides, stack_name, output, region, profile, template_file):
    """
    Implementation of the ``cli`` method
    """
    from samcli.commands.list.endpoints.endpoints_context import EndpointsContext

    with EndpointsContext(
        parameter_overrides=parameter_overrides,
        stack_name=stack_name,
        output=output,
        region=region,
        profile=profile,
        template_file=template_file,
    ) as endpoints_context:
        if not stack_name:
            stack_name_not_provided_message()
        endpoints_context.run()
