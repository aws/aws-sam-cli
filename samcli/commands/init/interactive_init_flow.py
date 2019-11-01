"""
Isolates interactive init prompt flow. Expected to call generator logic at end of flow.
"""
import click

from samcli.local.common.runtime_template import INIT_RUNTIMES, RUNTIME_TO_DEPENDENCY_MANAGERS
from samcli.commands.init.init_generator import do_generate
from samcli.commands.init.init_templates import InitTemplates


def do_interactive(location, runtime, dependency_manager, output_dir, name, app_template, no_input):
    if app_template:
        location_opt_choice = "1"
    else:
        click.echo("\t1 - Use an AWS-managed Application Template\n\t2 - Provide a Custom Template Location")
        location_opt_choice = click.prompt("Choice", type=click.Choice(["1", "2"]), show_choices=False)
    if location_opt_choice == "2":
        _generate_from_location(location, runtime, dependency_manager, output_dir, name, app_template, no_input)
    else:
        _generate_from_app_template(location, runtime, dependency_manager, output_dir, name, app_template)


def _generate_from_location(location, runtime, dependency_manager, output_dir, name, app_template, no_input):
    location = click.prompt("Template location (git, mercurial, http(s), zip, path)", type=str)
    if not output_dir:
        output_dir = click.prompt("Output Directory", type=click.Path(), default=".")
    do_generate(location, runtime, dependency_manager, output_dir, name, no_input, None)


def _generate_from_app_template(location, runtime, dependency_manager, output_dir, name, app_template):
    extra_context = None
    if not runtime:
        choices = list(map(str, range(1, len(INIT_RUNTIMES) + 1)))
        choice_num = 1
        click.echo("Which runtime would you like to use?")
        for r in INIT_RUNTIMES:
            msg = "\t" + str(choice_num) + " - " + r
            click.echo(msg)
            choice_num = choice_num + 1
        choice = click.prompt("Runtime", type=click.Choice(choices), show_choices=False)
        runtime = INIT_RUNTIMES[int(choice) - 1]  # zero index
        click.echo("Selected: " + runtime)
    if not dependency_manager:
        valid_dep_managers = RUNTIME_TO_DEPENDENCY_MANAGERS.get(runtime)
        if valid_dep_managers is None:
            dependency_manager = None
        elif len(valid_dep_managers) is 1:
            dependency_manager = valid_dep_managers[0]
            click.echo("Only one valid dependency manager, using " + dependency_manager)
        else:
            dependency_manager = click.prompt(
                "Dependency Manager", type=click.Choice(valid_dep_managers), default=valid_dep_managers[0]
            )
            click.echo("Selected " + dependency_manager + " as dependency manager.")
    if not name:
        name = click.prompt("Project Name", type=str, default="sam-app")
    templates = InitTemplates()
    if app_template is not None:
        location = templates.location_from_app_template(runtime, dependency_manager, app_template)
        extra_context = {"project_name": name, "runtime": runtime}
    else:
        location = templates.prompt_for_location(runtime, dependency_manager)
        extra_context = {"project_name": name, "runtime": runtime}
    no_input = True
    if not output_dir:
        click.echo(
            "The AWS SAM CLI defaults to creating your project in the current working directory, with the folder name matching your project name, for e.g. ./"
            + name
            + "\nChange the output_dir value to set a different root directory. For example, if the output dir is /tmp we will write the project to /tmp/"
            + name
        )
        output_dir = click.prompt("Output Directory", type=click.Path(), default=".")
    do_generate(location, runtime, dependency_manager, output_dir, name, no_input, extra_context)
