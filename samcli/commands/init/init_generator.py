"""
Cookiecutter-based generation logic for project templates.
"""

from samcli.commands.exceptions import UserException
from samcli.lib.init import generate_project
from samcli.lib.init.exceptions import GenerateProjectFailedError, ArbitraryProjectDownloadFailed


def do_generate(location, runtime, dependency_manager, output_dir, name, no_input, extra_context):
    try:
        generate_project(location, runtime, dependency_manager, output_dir, name, no_input, extra_context)
    except (GenerateProjectFailedError, ArbitraryProjectDownloadFailed) as e:
        raise UserException(str(e), wrapped_from=e.__class__.__name__) from e
