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
        click.echo("Which template source would you like to use?")
        click.echo("\t1 - AWS Quick Start Templates\n\t2 - Custom Template Location")
        location_opt_choice = click.prompt("Choice", type=click.Choice(["1", "2"]), show_choices=False)
    if location_opt_choice == "2":
        _generate_from_location(location, runtime, dependency_manager, output_dir, name, app_template, no_input)
    else:
        _generate_from_app_template(location, runtime, dependency_manager, output_dir, name, app_template)


def _generate_from_location(location, runtime, dependency_manager, output_dir, name, app_template, no_input):
    location = click.prompt("\nTemplate location (git, mercurial, http(s), zip, path)", type=str)
    summary_msg = """
-----------------------
Generating application:
-----------------------
Location: {location}
Output Directory: {output_dir}
    """.format(
        location=location, output_dir=output_dir
    )
    click.echo(summary_msg)
    do_generate(location, runtime, dependency_manager, output_dir, name, no_input, None)


# pylint: disable=too-many-statements
def _generate_from_app_template(location, runtime, dependency_manager, output_dir, name, app_template):
    extra_context = None
    if not runtime:
        choices = list(map(str, range(1, len(INIT_RUNTIMES) + 1)))
        choice_num = 1
        click.echo("\nWhich runtime would you like to use?")
        for r in INIT_RUNTIMES:
            msg = "\t" + str(choice_num) + " - " + r
            click.echo(msg)
            choice_num = choice_num + 1
        choice = click.prompt("Runtime", type=click.Choice(choices), show_choices=False)
        runtime = INIT_RUNTIMES[int(choice) - 1]  # zero index
    if not dependency_manager:
        valid_dep_managers = RUNTIME_TO_DEPENDENCY_MANAGERS.get(runtime)
        if valid_dep_managers is None:
            dependency_manager = None
        elif len(valid_dep_managers) == 1:
            dependency_manager = valid_dep_managers[0]
        else:
            choices = list(map(str, range(1, len(valid_dep_managers) + 1)))
            choice_num = 1
            click.echo("\nWhich dependency manager would you like to use?")
            for dm in valid_dep_managers:
                msg = "\t" + str(choice_num) + " - " + dm
                click.echo(msg)
                choice_num = choice_num + 1
            choice = click.prompt("Dependency manager", type=click.Choice(choices), show_choices=False)
            dependency_manager = valid_dep_managers[int(choice) - 1]  # zero index
    if not name:
        name = click.prompt("\nProject name", type=str, default="sam-app")
    templates = InitTemplates()
    if app_template is not None:
        location = templates.location_from_app_template(runtime, dependency_manager, app_template)
        extra_context = {"project_name": name, "runtime": runtime}
    else:
        location, app_template = templates.prompt_for_location(runtime, dependency_manager)
        extra_context = {"project_name": name, "runtime": runtime}
    no_input = True
    summary_msg = """
-----------------------
Generating application:
-----------------------
Name: {name}
Runtime: {runtime}
Dependency Manager: {dependency_manager}
Application Template: {app_template}
Output Directory: {output_dir}

Next steps can be found in the README file at {output_dir}/{name}/README.md
    """.format(
        name=name,
        runtime=runtime,
        dependency_manager=dependency_manager,
        app_template=app_template,
        output_dir=output_dir,
    )
    click.echo(summary_msg)
    do_generate(location, runtime, dependency_manager, output_dir, name, no_input, extra_context)
