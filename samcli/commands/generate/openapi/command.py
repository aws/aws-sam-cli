"""
CLI command for "generate openapi" command
"""

import click

from samcli.cli.cli_config_file import ConfigProvider, configuration_option
from samcli.cli.main import aws_creds_options, common_options, pass_context, print_cmdline_args
from samcli.commands._utils.command_exception_handler import command_exception_handler
from samcli.commands._utils.options import parameter_override_option, template_click_option
from samcli.lib.telemetry.metric import track_command
from samcli.lib.utils.version_checker import check_newer_version

SHORT_HELP = "Generate OpenAPI specification from SAM template."

DESCRIPTION = """
  Generate an OpenAPI (Swagger) specification document from a SAM template.
  
  SAM automatically generates OpenAPI documents for your APIs at deploy time. 
  This command allows you to access that generated OpenAPI document as part of 
  your build process, enabling integration with tools like swagger-codegen, 
  OpenAPI Generator, and other API documentation/client generation tools.
"""


@click.command(
    "openapi",
    short_help=SHORT_HELP,
    help=DESCRIPTION,
    context_settings={"max_content_width": 120},
)
@configuration_option(provider=ConfigProvider(section="parameters"))
@template_click_option(include_build=False)
@click.option(
    "--api-logical-id",
    required=False,
    type=str,
    help="Logical ID of the API resource to generate OpenAPI for. "
    "Required when template contains multiple APIs. "
    "Defaults to auto-detection when only one API exists.",
)
@click.option(
    "--output-file",
    "-o",
    required=False,
    type=click.Path(),
    help="Path to output file for generated OpenAPI document. " "If not specified, outputs to stdout.",
)
@click.option(
    "--format",
    type=click.Choice(["yaml", "json"], case_sensitive=False),
    default="yaml",
    help="Output format for the OpenAPI document.",
    show_default=True,
)
@click.option(
    "--openapi-version",
    type=click.Choice(["2.0", "3.0"], case_sensitive=False),
    default="3.0",
    help="OpenAPI specification version (2.0 = Swagger, 3.0 = OpenAPI).",
    show_default=True,
)
@parameter_override_option
@common_options
@aws_creds_options
@pass_context
@track_command
@check_newer_version
@print_cmdline_args
@command_exception_handler
def cli(
    ctx,
    template_file,
    api_logical_id,
    output_file,
    format,
    openapi_version,
    parameter_overrides,
    config_file,
    config_env,
):
    """
    `sam generate openapi` command entry point
    """
    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing

    do_cli(
        template_file=template_file,
        api_logical_id=api_logical_id,
        output_file=output_file,
        output_format=format,
        openapi_version=openapi_version,
        parameter_overrides=parameter_overrides,
        region=ctx.region,
        profile=ctx.profile,
    )  # pragma: no cover


def do_cli(
    template_file,
    api_logical_id,
    output_file,
    output_format,
    openapi_version,
    parameter_overrides,
    region,
    profile,
):
    """
    Implementation of the ``cli`` method
    """
    from samcli.commands.generate.openapi.context import OpenApiContext

    with OpenApiContext(
        template_file=template_file,
        api_logical_id=api_logical_id,
        output_file=output_file,
        output_format=output_format,
        openapi_version=openapi_version,
        parameter_overrides=parameter_overrides,
        region=region,
        profile=profile,
    ) as context:
        context.run()
