"""
Invokable Module for CLI

python -m samcli
"""

from samcli.cli.main import cli  # pragma: no cover

if __name__ == "__main__":  # pragma: no cover
    # NOTE(TheSriram): prog_name is always set to "sam". This way when the CLI is invoked as a module,
    # the help text that is generated still says "sam" instead of "__main__".
    cli(prog_name="sam")
