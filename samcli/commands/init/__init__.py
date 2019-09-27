# -*- coding: utf-8 -*-
"""
Init command to scaffold a project app from a template
"""
import logging

import click

from samcli.cli.main import pass_context, common_options
from samcli.commands.exceptions import UserException
from samcli.local.common.runtime_template import INIT_RUNTIMES, RUNTIME_TO_DEPENDENCY_MANAGERS, SUPPORTED_DEP_MANAGERS
from samcli.local.init import generate_project
from samcli.local.init.exceptions import GenerateProjectFailedError
from samcli.lib.telemetry.metrics import track_command

LOG = logging.getLogger(__name__)


@click.command(
    "init", short_help="Init an AWS SAM application.", context_settings=dict(help_option_names=[u"-h", u"--help"])
)
@click.option(
    "--no-interactive",
    is_flag=True,
    default=False,
    help="Disable interactive prompting for values, and fail if any required values are missing.",
)
@click.option("-l", "--location", help="Template location (git, mercurial, http(s), zip, path)")
@click.option("-r", "--runtime", type=click.Choice(INIT_RUNTIMES), help="Lambda Runtime of your app")
@click.option(
    "-d",
    "--dependency-manager",
    type=click.Choice(SUPPORTED_DEP_MANAGERS),
    default=None,
    help="Dependency manager of your Lambda runtime",
    required=False,
)
@click.option("-o", "--output-dir", type=click.Path(), help="Where to output the initialized app into")
@click.option("-n", "--name", help="Name of your project to be generated as a folder")
@click.option(
    "--no-input",
    is_flag=True,
    default=False,
    help="Disable prompting and accept default values defined template config",
)
@click.option(
    "--application-template",
    default=None,
    help="If using a managed AWS SAM CLI application template, provide its identifier.",
)
@common_options
@pass_context
@track_command
def cli(ctx, no_interactive, location, runtime, dependency_manager, output_dir, name, no_input, application_template):
    do_cli(
        ctx, no_interactive, location, runtime, dependency_manager, output_dir, name, no_input, application_template
    )  # pragma: no cover


def do_cli(ctx, no_interactive, location, runtime, dependency_manager, output_dir, name, no_input, app_template):
    # check for mutually exclusive parameters and fail
    if app_template and location:
        raise "You must not provide both --application-template and --location"

    # check for required parameters
    if name and ((runtime and app_template) or location):
        _do_generate(location, runtime, dependency_manager, output_dir, name, no_input, app_template)
    elif no_interactive:
        # raise error - this message is a slight mess, and hard to read
        error_msg = """
ERROR: Missing required parameters, with --no-interactive set.

Must provide at one of the following required parameter combinations:
    --name and --application-template and --runtime
    --name and --location

You can also re-run without the --no-interactive flag to be prompted for required values.
        """
        raise UserException(error_msg)
    else:
        # proceed to interactive state machine, which will call _do_generate
        _do_interactive(location, runtime, dependency_manager, output_dir, name, no_input, app_template)


def _do_interactive(location, runtime, dependency_manager, output_dir, name, no_input, app_template):
    if not name:
        name = click.prompt("Project Name", type=str)
    if not location:
        if not runtime:
            # TODO: Better output than click default choices.
            runtime = click.prompt("Runtime", type=click.Choice(INIT_RUNTIMES))
        # TODO: Only fetch this for default app templates? Don't want to give a false impression of all templates being
        # available for multiple dependency managers.
        if not dependency_manager:
            valid_dep_managers = RUNTIME_TO_DEPENDENCY_MANAGERS.get(runtime)
            if valid_dep_managers is None:
                dependency_manager = None
            else:
                dependency_manager = click.prompt(
                    "Dependency Manager", type=click.Choice(valid_dep_managers), default=valid_dep_managers[0]
                )
        if not (location or app_template):
            # pull app template choices from github and display
            # with alternate option to pick custom, which prompts location
            templates_folder = _clone_app_templates
            app_template_options = _get_manifest_options(runtime, templates_folder)
            app_template_options.append("Custom Template")
            # this should display with number codes for selection - 
            at_choice = click.prompt("Template", type=click.Choice(app_template_options))
            if at_choice is "Custom Template":
                print("Doc Link for Valid Options: ***")
                location = click.prompt("App Template Location", type=str)
            else:
                # location is in the local filepath - send extra context to cookiecutter
                location = _get_app_template_folder(templates_folder, at_choice)
        if not output_dir:
            output_dir = click.prompt("Output Directory", type=click.Path(), default=".")
    _do_generate(location, runtime, dependency_manager, output_dir, name, no_input, app_template)


def _clone_app_templates():
    return None


def _get_app_template_folder(templates_folder, app_template_choice):
    return None


def _get_manifest_options(runtime, templates_folder):
    return ["Option 1", "Option 2"]


def _do_generate(location, runtime, dependency_manager, output_dir, name, no_input, app_template):
    # Todo: This needs to handle app_template
    no_build_msg = """
Project generated: {output_dir}/{name}

Steps you can take next within the project folder
===================================================
[*] Invoke Function: sam local invoke HelloWorldFunction --event event.json
[*] Start API Gateway locally: sam local start-api
""".format(
        output_dir=output_dir, name=name
    )

    build_msg = """
Project generated: {output_dir}/{name}

Steps you can take next within the project folder
===================================================
[*] Install dependencies
[*] Invoke Function: sam local invoke HelloWorldFunction --event event.json
[*] Start API Gateway locally: sam local start-api
""".format(
        output_dir=output_dir, name=name
    )

    no_build_step_required = (
        "python",
        "python3.7",
        "python3.6",
        "python2.7",
        "nodejs",
        "nodejs4.3",
        "nodejs6.10",
        "nodejs8.10",
        "nodejs10.x",
        "ruby2.5",
    )
    next_step_msg = no_build_msg if runtime in no_build_step_required else build_msg
    try:
        generate_project(location, runtime, dependency_manager, output_dir, name, no_input)
        if not location:
            click.secho(next_step_msg, bold=True)
            click.secho("Read {name}/README.md for further instructions\n".format(name=name), bold=True)
        click.secho("[*] Project initialization is now complete", fg="green")
    except GenerateProjectFailedError as e:
        raise UserException(str(e))
