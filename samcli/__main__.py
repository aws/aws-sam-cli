"""
Invokable Module for CLI

python -m samcli
"""

import sys
from samcli.cli.main import cli

if __name__ == "__main__":
    sys.exit(cli())
