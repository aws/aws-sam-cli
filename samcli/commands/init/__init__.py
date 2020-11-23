# -*- coding: utf-8 -*-
"""
Init command to scaffold a project app from a template
"""
import logging
import json
from json import JSONDecodeError

import click

from samcli.cli.cli_config_file import configuration_option, TomlProvider
from samcli.cli.main import pass_context, common_options
from samcli.local.common.runtime_template import RUNTIMES, SUPPORTED_DEP_MANAGERS
from samcli.lib.telemetry.metrics import track_command

LOG = logging.getLogger(__name__)

HELP_TEXT = """ \b
    Initialize a serverless application with a SAM template, folder
    structure for your Lambda functions, connected to an event source such as APIs,
    S3 Buckets or DynamoDB Tables. This application includes everything you need to
    get started with serverless and eventually grow into a production scale application.
    \b
    This command can initialize a boilerplate serverless app. If you want to create your own
    template as well as use a custom location please take a look at our official documentation.
\b
Common usage:
    \b
    Starts an interactive prompt process to initialize a new project:
    \b
    $ sam init
    \b
    Initializes a new SAM project using project templates without an interactive workflow:
    \b
    $ sam init --name sam-app --runtime nodejs10.x --dependency-manager npm --app-template hello-world
    \b
    Initializes a new SAM project using custom template in a Git/Mercurial repository
    \b
    # gh being expanded to github url
    $ sam init --location gh:aws-samples/cookiecutter-aws-sam-python
    \b
    $ sam init --location git+ssh://git@github.com/aws-samples/cookiecutter-aws-sam-python.git
    \b
    $ sam init --location hg+ssh://hg@bitbucket.org/repo/template-name
    \b
    Initializes a new SAM project using custom template in a Zipfile
    \b
    $ sam init --location /path/to/template.zip
    \b
    $ sam init --location https://example.com/path/to/template.zip
    \b
    Initializes a new SAM project using custom template in a local path
    \b
    $ sam init --location /path/to/template/folder
"""


@click.command(
    "init",
    help=HELP_TEXT,
    short_help="Init an AWS SAM application.",
    context_settings=dict(help_option_names=["-h", "--help"]),
)
@configuration_option(provider=TomlProvider(section="parameters"))
@click.option(
    "--no-interactive",
    is_flag=True,
    default=False,
    help="Disable interactive prompting for init parameters, and fail if any required values are missing.",
)
@click.option("-l", "--location", help="Template location (git, mercurial, http(s), zip, path)")
@click.option("-r", "--runtime", type=click.Choice(RUNTIMES), help="Lambda Runtime of your app")
@click.option(
    "-d",
    "--dependency-manager",
    type=click.Choice(SUPPORTED_DEP_MANAGERS),
    default=None,
    help="Dependency manager of your Lambda runtime",
    required=False,
)
@click.option("-o", "--output-dir", type=click.Path(), help="Where to output the initialized app into", default=".")
@click.option("-n", "--name", help="Name of your project to be generated as a folder")
@click.option(
    "--app-template",
    help="Identifier of the managed application template you want to use. If not sure, call 'sam init' without options for an interactive workflow.",
)
@click.option(
    "--no-input",
    is_flag=True,
    default=False,
    help="Disable Cookiecutter prompting and accept default values defined template config",
)
@click.option(
    "--extra-context",
    default=None,
    help="Override any custom parameters in the template's cookiecutter.json configuration e.g. "
    ""
    '{"customParam1": "customValue1", "customParam2":"customValue2"}'
    """ """,
    required=False,
)
@common_options
@pass_context
@track_command
def cli(
    ctx,
    no_interactive,
    location,
    runtime,
    dependency_manager,
    output_dir,
    name,
    app_template,
    no_input,
    extra_context,
    config_file,
    config_env,
):
    do_cli(
        ctx,
        no_interactive,
        location,
        runtime,
        dependency_manager,
        output_dir,
        name,
        app_template,
        no_input,
        extra_context,
    )  # pragma: no cover


# pylint: disable=too-many-locals
def do_cli(
    ctx,
    no_interactive,
    location,
    runtime,
    dependency_manager,
    output_dir,
    name,
    app_template,
    no_input,
    extra_context,
    auto_clone=True,
):
    from samcli.commands.init.init_generator import do_generate
    from samcli.commands.init.interactive_init_flow import do_interactive
    from samcli.commands.init.init_templates import InitTemplates

    _deprecate_notification(runtime)

    # check for mutually exclusive parameters
    if location and app_template:
        msg = """
You must not provide both the --location and --app-template parameters.

You can run 'sam init' without any options for an interactive initialization flow, or you can provide one of the following required parameter combinations:
    --name and --runtime and --app-template and --dependency-manager
    --location
        """
        raise click.UsageError(msg)
    # check for required parameters
    if location or (name and runtime and dependency_manager and app_template):
        # need to turn app_template into a location before we generate
        if app_template:
            templates = InitTemplates(no_interactive, auto_clone)
            location = templates.location_from_app_template(runtime, dependency_manager, app_template)
            no_input = True
        extra_context = _get_cookiecutter_template_context(name, runtime, extra_context)

        if not output_dir:
            output_dir = "."
        do_generate(location, runtime, dependency_manager, output_dir, name, no_input, extra_context)
    elif no_interactive:
        error_msg = """
ERROR: Missing required parameters, with --no-interactive set.

Must provide one of the following required parameter combinations:
    --name and --runtime and --dependency-manager and --app-template
    --location

You can also re-run without the --no-interactive flag to be prompted for required values.
        """
        raise click.UsageError(error_msg)
    else:
        # proceed to interactive state machine, which will call do_generate
        do_interactive(location, runtime, dependency_manager, output_dir, name, app_template, no_input)


def _deprecate_notification(runtime):
    from samcli.lib.utils.colors import Colored

    deprecated_runtimes = {"dotnetcore1.0", "dotnetcore2.0"}
    if runtime in deprecated_runtimes:
        message = (
            f"WARNING: {runtime} is no longer supported by AWS Lambda, please update to a newer supported runtime. SAM CLI "
            f"will drop support for all deprecated runtimes {deprecated_runtimes} on May 1st. "
            f"See issue: https://github.com/awslabs/aws-sam-cli/issues/1934 for more details."
        )
        LOG.warning(Colored().yellow(message))


def _get_cookiecutter_template_context(name, runtime, extra_context):
    default_context = {}
    extra_context_dict = {}

    if runtime is not None:
        default_context["runtime"] = runtime

    if name is not None:
        default_context["project_name"] = name

    if extra_context is not None:
        try:
            extra_context_dict = json.loads(extra_context)
        except JSONDecodeError as ex:
            raise click.UsageError(
                "Parse error reading the --extra-context parameter. The value of this parameter must be valid JSON."
            ) from ex

    return {**extra_context_dict, **default_context}
