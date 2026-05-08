"""
Shared options for execution history commands
"""

from typing import Dict, List

from samcli.cli.core.options import add_common_options_info

# Common options between local and remote execution history commands
COMMON_EXECUTION_HISTORY_FORMATTING_OPTIONS: List[str] = ["format"]

# All options for history commands
COMMON_EXECUTION_HISTORY_OPTIONS: List[str] = COMMON_EXECUTION_HISTORY_FORMATTING_OPTIONS

# Formatting options info only
COMMON_EXECUTION_HISTORY_FORMATTING_OPTIONS_INFO: Dict[str, Dict] = {
    "Formatting Options": {
        "option_names": {opt: {"rank": idx} for idx, opt in enumerate(COMMON_EXECUTION_HISTORY_FORMATTING_OPTIONS)}
    },
}

# Complete options info with common options included
COMMON_EXECUTION_HISTORY_OPTIONS_INFO: Dict[str, Dict] = COMMON_EXECUTION_HISTORY_FORMATTING_OPTIONS_INFO.copy()
add_common_options_info(COMMON_EXECUTION_HISTORY_OPTIONS_INFO)
