from samcli.cli.command import _SAM_CLI_COMMAND_PACKAGES

SAM_CLI_HIDDEN_IMPORTS = _SAM_CLI_COMMAND_PACKAGES + [
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
