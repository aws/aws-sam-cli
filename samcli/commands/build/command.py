"""
CLI command for "build" command
"""

import os
import logging
import click

from samcli.commands.exceptions import UserException
from samcli.cli.main import pass_context, common_options as cli_framework_options, aws_creds_options
from samcli.commands._utils.options import template_option_without_build, docker_common_options, \
    parameter_override_option
from samcli.commands.build.build_context import BuildContext
from samcli.lib.build.app_builder import ApplicationBuilder, BuildError, UnsupportedBuilderLibraryVersionError, \
    ContainerBuildNotSupported
from samcli.lib.build.workflow_config import UnsupportedRuntimeException
from samcli.local.lambdafn.exceptions import FunctionNotFound
from samcli.commands._utils.template import move_template

LOG = logging.getLogger(__name__)

DEFAULT_BUILD_DIR = os.path.join(".aws-sam", "build")

HELP_TEXT = """
Use this command to build your AWS Lambda Functions source code to generate artifacts that target AWS Lambda's
execution environment.\n
\b
Supported Resource Types
------------------------
1. AWS::Serverless::Function\n
2. AWS::Lambda::Function\n
\b
Supported Runtimes
------------------
1. Python 2.7, 3.6, 3.7 using PIP\n
2. Nodejs 10.x, 8.10, 6.10 using NPM\n
3. Ruby 2.5 using Bundler\n
4. Java 8 using Gradle\n
5. Dotnetcore2.0 and 2.1 using Dotnet CLI (without --use-container flag)\n
\b
Examples
--------
To use this command, update your SAM template to specify the path
to your function's source code in the resource's Code or CodeUri property.
\b
To build on your workstation, run this command in folder containing
SAM template. Built artifacts will be written to .aws-sam/build folder
$ sam build\n
\b
To build inside a AWS Lambda like Docker container
$ sam build --use-container
\b
To build & run your functions locally
$ sam build && sam local invoke
\b
To build and package for deployment
$ sam build && sam package --s3-bucket <bucketname>
"""


@click.command("build", help=HELP_TEXT, short_help="Build your Lambda function code")
@click.option('--build-dir', '-b',
              default=DEFAULT_BUILD_DIR,
              type=click.Path(file_okay=False, dir_okay=True, writable=True),  # Must be a directory
              help="Path to a folder where the built artifacts will be stored")
@click.option("--base-dir", "-s",
              default=None,
              type=click.Path(dir_okay=True, file_okay=False),  # Must be a directory
              help="Resolve relative paths to function's source code with respect to this folder. Use this if "
                   "SAM template and your source code are not in same enclosing folder. By default, relative paths "
                   "are resolved with respect to the SAM template's location")
@click.option("--use-container", "-u",
              is_flag=True,
              help="If your functions depend on packages that have natively compiled dependencies, use this flag "
                   "to build your function inside an AWS Lambda-like Docker container")
@click.option("--manifest", "-m",
              default=None,
              type=click.Path(),
              help="Path to a custom dependency manifest (ex: package.json) to use instead of the default one")
@template_option_without_build
@parameter_override_option
@docker_common_options
@cli_framework_options
@aws_creds_options
@click.argument('function_identifier', required=False)
@pass_context
def cli(ctx,
        function_identifier,
        template,
        base_dir,
        build_dir,
        use_container,
        manifest,
        docker_network,
        skip_pull_image,
        parameter_overrides,
        ):
    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing

    mode = _get_mode_value_from_envvar("SAM_BUILD_MODE", choices=["debug"])

    do_cli(function_identifier, template, base_dir, build_dir, True, use_container, manifest, docker_network,
           skip_pull_image, parameter_overrides, mode)  # pragma: no cover


def do_cli(function_identifier,  # pylint: disable=too-many-locals
           template,
           base_dir,
           build_dir,
           clean,
           use_container,
           manifest_path,
           docker_network,
           skip_pull_image,
           parameter_overrides,
           mode):
    """
    Implementation of the ``cli`` method
    """

    LOG.debug("'build' command is called")

    if use_container:
        LOG.info("Starting Build inside a container")

    with BuildContext(function_identifier,
                      template,
                      base_dir,
                      build_dir,
                      clean=clean,
                      manifest_path=manifest_path,
                      use_container=use_container,
                      parameter_overrides=parameter_overrides,
                      docker_network=docker_network,
                      skip_pull_image=skip_pull_image,
                      mode=mode) as ctx:
        try:
            builder = ApplicationBuilder(ctx.functions_to_build,
                                         ctx.build_dir,
                                         ctx.base_dir,
                                         manifest_path_override=ctx.manifest_path_override,
                                         container_manager=ctx.container_manager,
                                         mode=ctx.mode)
        except FunctionNotFound as ex:
            raise UserException(str(ex))

        try:
            artifacts = builder.build()
            modified_template = builder.update_template(ctx.template_dict,
                                                        ctx.original_template_path,
                                                        artifacts)

            move_template(ctx.original_template_path,
                          ctx.output_template_path,
                          modified_template)

            click.secho("\nBuild Succeeded", fg="green")

            msg = gen_success_msg(os.path.relpath(ctx.build_dir),
                                  os.path.relpath(ctx.output_template_path),
                                  os.path.abspath(ctx.build_dir) == os.path.abspath(DEFAULT_BUILD_DIR))

            click.secho(msg, fg="yellow")

        except (UnsupportedRuntimeException, BuildError, UnsupportedBuilderLibraryVersionError,
                ContainerBuildNotSupported) as ex:
            click.secho("\nBuild Failed", fg="red")
            raise UserException(str(ex))


def gen_success_msg(artifacts_dir, output_template_path, is_default_build_dir):

    invoke_cmd = "sam local invoke"
    if not is_default_build_dir:
        invoke_cmd += " -t {}".format(output_template_path)

    package_cmd = "sam package --s3-bucket <yourbucket>"
    if not is_default_build_dir:
        package_cmd += " --template-file {}".format(output_template_path)

    msg = """\nBuilt Artifacts  : {artifacts_dir}
Built Template   : {template}

Commands you can use next
=========================
[*] Invoke Function: {invokecmd}
[*] Package: {packagecmd}
    """.format(invokecmd=invoke_cmd,
               packagecmd=package_cmd,
               artifacts_dir=artifacts_dir,
               template=output_template_path)

    return msg


def _get_mode_value_from_envvar(name, choices):

    mode = os.environ.get(name, None)
    if not mode:
        return None

    if mode not in choices:
        raise click.UsageError("Invalid value for 'mode': invalid choice: {}. (choose from {})"
                               .format(mode, choices))

    return mode
