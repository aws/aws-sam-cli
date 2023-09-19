"""
Sets up the cli for resources
"""

import click

from samcli.cli.cli_config_file import ConfigProvider, configuration_option, save_params_option
from samcli.cli.main import aws_creds_options, common_options, pass_context, print_cmdline_args
from samcli.commands._utils.command_exception_handler import command_exception_handler
from samcli.commands._utils.options import parameter_override_option, template_option_without_build
from samcli.commands.list.cli_common.options import output_option, stack_name_not_provided_message, stack_name_option
from samcli.lib.telemetry.metric import track_command
from samcli.lib.utils.version_checker import check_newer_version

HELP_TEXT = """
Get a list of resources that will be deployed to CloudFormation.\n
If a stack name is provided, the corresponding physical IDs of each
resource will be mapped to the logical ID of each resource.
"""


@click.command(name="resources", help=HELP_TEXT)
@configuration_option(provider=ConfigProvider(section="parameters"))
@parameter_override_option
@stack_name_option
@output_option
@template_option_without_build
@aws_creds_options
@common_options
@save_params_option
@pass_context
@track_command
@check_newer_version
@print_cmdline_args
@command_exception_handler
def cli(self, parameter_overrides, stack_name, output, template_file, save_params, config_file, config_env):
    """
    `sam list resources` command entry point
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
    from samcli.commands.list.resources.resources_context import ResourcesContext

    with ResourcesContext(
        parameter_overrides=parameter_overrides,
        stack_name=stack_name,
        output=output,
        region=region,
        profile=profile,
        template_file=template_file,
    ) as resources_context:
        if not stack_name:
            stack_name_not_provided_message()
        resources_context.run()
