"""
Options configuration for remote execution get command
"""

from typing import Dict, List

from samcli.commands.common.execution.get.options import (
    COMMON_EXECUTION_GET_FORMATTING_OPTIONS,
    COMMON_EXECUTION_GET_FORMATTING_OPTIONS_INFO,
)
from samcli.commands.remote.core.options import (
    ALL_OPTIONS as REMOTE_CORE_OPTIONS,
)
from samcli.commands.remote.core.options import (
    OPTIONS_INFO as REMOTE_CORE_OPTIONS_INFO,
)

# All options available for the remote get command
ALL_OPTIONS: List[str] = COMMON_EXECUTION_GET_FORMATTING_OPTIONS + REMOTE_CORE_OPTIONS

# Options information for formatting help text
OPTIONS_INFO: Dict[str, Dict] = COMMON_EXECUTION_GET_FORMATTING_OPTIONS_INFO.copy()
OPTIONS_INFO.update(REMOTE_CORE_OPTIONS_INFO)
