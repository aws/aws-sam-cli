"""
Options configuration for remote execution history command
"""

from typing import Dict, List

from samcli.commands.common.execution.history.options import (
    COMMON_EXECUTION_HISTORY_OPTIONS,
    COMMON_EXECUTION_HISTORY_OPTIONS_INFO,
)
from samcli.commands.remote.core.options import (
    ALL_OPTIONS as REMOTE_CORE_OPTIONS,
)
from samcli.commands.remote.core.options import (
    OPTIONS_INFO as REMOTE_CORE_OPTIONS_INFO,
)

# All options available for the remote history command
ALL_OPTIONS: List[str] = COMMON_EXECUTION_HISTORY_OPTIONS + REMOTE_CORE_OPTIONS

# Options information for formatting help text
OPTIONS_INFO: Dict[str, Dict] = COMMON_EXECUTION_HISTORY_OPTIONS_INFO.copy()
OPTIONS_INFO.update(REMOTE_CORE_OPTIONS_INFO)
