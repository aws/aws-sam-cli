"""
Keeps list of hidden/dynamic imports that is being used in SAM CLI, so that pyinstaller can include these packages
"""
from samcli.cli.command import _SAM_CLI_COMMAND_PACKAGES

SAM_CLI_HIDDEN_IMPORTS = _SAM_CLI_COMMAND_PACKAGES + [
    # terraform hook
    "samcli.hook_packages.terraform",
    "cookiecutter.extensions",
    "jinja2_time",
    "text_unidecode",
    "samtranslator",
    # default hidden import 'pkg_resources.py2_warn' is added
    # since pyInstaller 4.0.
    "pkg_resources.py2_warn",
    "aws_lambda_builders.workflows",
    "configparser",
]
