"""
Options configuration for local callback heartbeat command
"""

from typing import Dict

from samcli.cli.core.options import add_common_options_info

# Options information for formatting help text
OPTIONS_INFO: Dict[str, Dict] = {}
add_common_options_info(OPTIONS_INFO)
