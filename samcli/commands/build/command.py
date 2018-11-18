"""
CLI command for "build" command
"""

import os
import logging
import click

from samcli.commands.exceptions import UserException
from samcli.yamlhelper import yaml_dump
from samcli.cli.main import pass_context, common_options as cli_framework_options, aws_creds_options
from samcli.commands._utils.options import template_option_without_build, docker_common_options
from samcli.commands.build.build_context import BuildContext
from samcli.lib.build.app_builder import ApplicationBuilder, UnsupportedRuntimeException, \
    BuildError, UnsupportedBuilderLibraryVersionError

LOG = logging.getLogger(__name__)


HELP_TEXT = """
Use this command to build your Lambda function source code and generate artifacts that can be deployed to AWS Lambda
"""


@click.command("build", help=HELP_TEXT, short_help="Build your Lambda function code")
@click.option('--build-dir', '-b',
              default=os.path.join(".aws-sam", "build"),
              type=click.Path(file_okay=False, dir_okay=True, writable=True),  # Must be a directory
              help="Path to a folder where the built artifacts will be stored")
@click.option("--base-dir", "-s",
              default=None,
              type=click.Path(dir_okay=True, file_okay=False),  # Must be a directory
              help="Resolve relative paths to function's source code with respect to this folder. Use this if "
                   "SAM template and your source code are not in same enclosing folder. By default, relative paths to"
                   "are resolved with respect to the SAM template's location")
@click.option("--use-container", "-n",
              is_flag=True,
              help="Run the builds inside a Docker container that simulates an AWS Lambda like environment")
@click.option("--manifest", "-m",
              default=None,
              type=click.Path(),
              help="Path to a custom dependency manifest (ex: package.json) to use instead of the default one")
@template_option_without_build
@docker_common_options
@cli_framework_options
@aws_creds_options
@pass_context
def cli(ctx,
        template,
        base_dir,
        build_dir,
        use_container,
        manifest,
        docker_network,
        skip_pull_image):
    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing

    do_cli(template, base_dir, build_dir, True, use_container, manifest, docker_network,
           skip_pull_image)  # pragma: no cover


def do_cli(template,
           base_dir,
           build_dir,
           clean,
           use_container,
           manifest_path,
           docker_network,
           skip_pull_image):
    """
    Implementation of the ``cli`` method
    """

    LOG.debug("'build' command is called")

    if use_container:
        LOG.info("Starting Build inside a container")

    with BuildContext(template,
                      base_dir,
                      build_dir,
                      clean=clean,
                      manifest_path=manifest_path,
                      use_container=use_container,
                      docker_network=docker_network,
                      skip_pull_image=skip_pull_image) as ctx:

        builder = ApplicationBuilder(ctx.function_provider,
                                     ctx.build_dir,
                                     ctx.base_dir,
                                     manifest_path_override=ctx.manifest_path_override,
                                     container_manager=ctx.container_manager
                                     )
        try:
            artifacts = builder.build()
            modified_template = builder.update_template(ctx.template_dict,
                                                        ctx.output_template_path,
                                                        artifacts)

            with open(ctx.output_template_path, "w") as fp:
                fp.write(yaml_dump(modified_template))

            msg = """\nBuild Artifacts Available At: {artifacts_dir}

Next Steps
==========
[*] Invoke Function: sam local invoke -t {template}
[*] Package: sam package --template-file {template}
            """.format(artifacts_dir=os.path.relpath(ctx.build_dir),
                       template=os.path.relpath(ctx.output_template_path))

            click.secho("\nBuild Succeeded", fg="green")

            click.secho(msg, fg="yellow")

        except (UnsupportedRuntimeException, BuildError, UnsupportedBuilderLibraryVersionError) as ex:
            click.secho("Build Failed", fg="red")
            raise UserException(str(ex))
