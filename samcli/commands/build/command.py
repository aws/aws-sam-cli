"""
CLI command for "build" command
"""

import os
import logging
import click

from samcli.yamlhelper import yaml_dump
from samcli.cli.main import pass_context, common_options as cli_framework_options, aws_creds_options
from samcli.commands._utils.options import template_common_option as template_option, docker_common_options
from samcli.commands.build.build_context import BuildContext
from samcli.lib.build.app_builder import ApplicationBuilder

LOG = logging.getLogger(__name__)

HELP_TEXT = """
Use this command to build your Lambda function source code and generate artifacts that can be deployed to AWS Lambda 
"""


@click.command("build", help=HELP_TEXT, short_help="Build your Lambda function code")
@click.option('--build-dir', '-b',
              default="build",
              type=click.Path(),
              help="Path to a folder where the built artifacts will be stored")
@click.option("--source-root", "-s",
              default=os.getcwd(),
              type=click.Path(),
              help="Resolve relative paths to function's source code with respect to this folder. Use this if "
                   "SAM template and your source code are not in same enclosing folder")
@click.option("--native", "-n",
              is_flag=True,
              help="Run the builds inside a AWS Lambda like Docker container")
@click.option("--clean", "-c",
              is_flag=True,
              help="Do a clean build by first deleting everything within the build directory")
@template_option
@docker_common_options
@cli_framework_options
@aws_creds_options
@pass_context
def cli(ctx,
        template,
        source_root,
        build_dir,
        clean,
        native,
        docker_network,
        skip_pull_image):
    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing

    do_cli(template, source_root, build_dir, clean, native, docker_network, skip_pull_image)  # pragma: no cover


def do_cli(template, source_root, build_dir, clean, use_container, docker_network, skip_pull_image):
    """
    Implementation of the ``cli`` method
    """

    LOG.debug("'build' command is called")

    with BuildContext(template,
                      source_root,
                      build_dir,
                      clean=True,   # TODO: Forcing a clean build for testing. REmove this
                      use_container=use_container,
                      docker_network=docker_network,
                      skip_pull_image=skip_pull_image) as ctx:

        builder = ApplicationBuilder(ctx.function_provider,
                                     ctx.build_dir,
                                     ctx.source_root,
                                     container_manager=ctx.container_manager,
                                     )
        artifacts = builder.build()
        modified_template = builder.update_template(ctx.template_dict,
                                                    ctx.output_template_path,
                                                    artifacts)

        with open(ctx.output_template_path, "w") as fp:
            fp.write(yaml_dump(modified_template))

