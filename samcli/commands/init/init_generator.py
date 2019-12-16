"""
Cookiecutter-based generation logic for project templates.
"""

from samcli.commands.exceptions import UserException
from lib.init import generate_project
from lib.init import GenerateProjectFailedError, ArbitraryProjectDownloadFailed


def do_generate(location, runtime, dependency_manager, output_dir, name, no_input, extra_context):
    try:
        generate_project(location, runtime, dependency_manager, output_dir, name, no_input, extra_context)
    except (GenerateProjectFailedError, ArbitraryProjectDownloadFailed) as e:
        raise UserException(str(e))
