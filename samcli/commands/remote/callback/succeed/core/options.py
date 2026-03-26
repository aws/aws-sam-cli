"""
Options configuration for remote callback succeed command
"""

from typing import Dict

from samcli.commands.common.callback.succeed.options import (
    COMMON_CALLBACK_SUCCEED_OPTIONS,
    COMMON_CALLBACK_SUCCEED_OPTIONS_INFO,
)
from samcli.commands.remote.core.options import ALL_OPTIONS as REMOTE_CORE_OPTIONS
from samcli.commands.remote.core.options import OPTIONS_INFO as REMOTE_CORE_OPTIONS_INFO

# All options available for the remote succeed command
ALL_OPTIONS = COMMON_CALLBACK_SUCCEED_OPTIONS + REMOTE_CORE_OPTIONS

# Options information for formatting help text
OPTIONS_INFO: Dict[str, Dict] = COMMON_CALLBACK_SUCCEED_OPTIONS_INFO.copy()
OPTIONS_INFO.update(REMOTE_CORE_OPTIONS_INFO)
