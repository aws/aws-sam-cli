"""
Invokable Module for CLI

python -m samcli
"""

from samcli.cli.main import cli  # pragma: no cover
from samcli.lib.utils.hook_script import run_hook_script_if_requested  # pragma: no cover

if __name__ == "__main__":  # pragma: no cover
    # A bundle runs cookiecutter's Python hooks by re-launching itself, so claim those invocations
    # before the CLI treats the script path as a command name.
    run_hook_script_if_requested()
    # NOTE(TheSriram): prog_name is always set to "sam". This way when the CLI is invoked as a module,
    # the help text that is generated still says "sam" instead of "__main__".
    cli(prog_name="sam")
