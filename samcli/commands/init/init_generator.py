"""
Cookiecutter-based generation logic for project templates.
"""

from samcli.commands.exceptions import UserException
from samcli.lib.init import generate_project
from samcli.lib.init.exceptions import InitErrorException


def do_generate(
    location,
    package_type,
    runtime,
    dependency_manager,
    output_dir,
    name,
    no_input,
    extra_context,
    tracing,
    application_insights,
):
    try:
        generate_project(
            location,
            package_type,
            runtime,
            dependency_manager,
            output_dir,
            name,
            no_input,
            extra_context,
            tracing,
            application_insights,
        )
    except InitErrorException as e:
        raise UserException(str(e), wrapped_from=e.__class__.__name__) from e
