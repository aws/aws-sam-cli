"""
Isolates interactive init prompt flow. Expected to call generator logic at end of flow.
"""
import click

from samcli.local.common.runtime_template import RUNTIMES, RUNTIME_TO_DEPENDENCY_MANAGERS
from samcli.commands.init.init_generator import do_generate
from samcli.commands.init.init_templates import InitTemplates


def do_interactive(location, runtime, dependency_manager, output_dir, name, app_template, no_input):
    if location:
        if not output_dir:
            output_dir = click.prompt("Output Directory", type=click.Path(), default=".")
        do_generate(location, runtime, dependency_manager, output_dir, name, no_input, None)
    else:
        if app_template:
            location_opt_choice = "1"
        else:
            click.echo("1 - Use a Managed Application Template\n2 - Provide a Custom Location")
            location_opt_choice = click.prompt("Location Choice", type=click.Choice(["1", "2"]), show_choices=False)
        if location_opt_choice == "2":
            _generate_from_location(location, runtime, dependency_manager, output_dir, name, app_template, no_input)
        else:
            _generate_from_app_template(location, runtime, dependency_manager, output_dir, name, app_template, no_input)


def _generate_from_location(location, runtime, dependency_manager, output_dir, name, app_template, no_input):
    location = click.prompt("Template location (git, mercurial, http(s), zip, path)", type=str)
    if not output_dir:
        output_dir = click.prompt("Output Directory", type=click.Path(), default=".")
    do_generate(location, runtime, dependency_manager, output_dir, name, no_input, None)


def _generate_from_app_template(location, runtime, dependency_manager, output_dir, name, app_template, no_input):
    extra_context = None
    if not name:
        name = click.prompt("Project Name", type=str)
    if not runtime:
        runtime = click.prompt("Runtime", type=click.Choice(RUNTIMES))
    if not dependency_manager:
        valid_dep_managers = RUNTIME_TO_DEPENDENCY_MANAGERS.get(runtime)
        if valid_dep_managers is None:
            dependency_manager = None
        else:
            dependency_manager = click.prompt(
                "Dependency Manager", type=click.Choice(valid_dep_managers), default=valid_dep_managers[0]
            )
    templates = InitTemplates()
    if app_template is not None:
        location = templates.location_from_app_template(runtime, dependency_manager, app_template)
        no_input = True
        extra_context = {"project_name": name, "runtime": runtime}
    else:
        location = templates.prompt_for_location(runtime, dependency_manager)
        no_input = True  # because we specified the template ourselves
        extra_context = {"project_name": name, "runtime": runtime}
    if not output_dir:
        output_dir = click.prompt("Output Directory", type=click.Path(), default=".")
    do_generate(location, runtime, dependency_manager, output_dir, name, no_input, extra_context)
