"""
Options configuration for local callback succeed command
"""

from typing import Dict

from samcli.cli.core.options import add_common_options_info
from samcli.commands.common.callback.succeed.options import COMMON_CALLBACK_SUCCEED_OPTIONS_INFO

# Options information for formatting help text
OPTIONS_INFO: Dict[str, Dict] = COMMON_CALLBACK_SUCCEED_OPTIONS_INFO.copy()
add_common_options_info(OPTIONS_INFO)
