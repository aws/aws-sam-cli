"""
Options configuration for remote callback heartbeat command
"""

from typing import Dict

from samcli.commands.common.callback.heartbeat.options import COMMON_CALLBACK_HEARTBEAT_OPTIONS
from samcli.commands.remote.core.options import ALL_OPTIONS as REMOTE_CORE_OPTIONS
from samcli.commands.remote.core.options import OPTIONS_INFO as REMOTE_CORE_OPTIONS_INFO

# All options available for the remote heartbeat command
ALL_OPTIONS = COMMON_CALLBACK_HEARTBEAT_OPTIONS + REMOTE_CORE_OPTIONS

# Options information for formatting help text
OPTIONS_INFO: Dict[str, Dict] = REMOTE_CORE_OPTIONS_INFO.copy()
