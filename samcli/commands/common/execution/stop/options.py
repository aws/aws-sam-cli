"""
Shared options for execution stop commands
"""

from typing import Dict, List

from samcli.cli.core.options import add_common_options_info

# Common options between local and remote stop commands
COMMON_EXECUTION_STOP_OPTIONS: List[str] = ["error_message", "error_type", "error_data", "stack_trace"]

# Common options info with common options included
COMMON_EXECUTION_STOP_OPTIONS_INFO: Dict[str, Dict] = {
    "Stop Options": {"option_names": {opt: {"rank": idx} for idx, opt in enumerate(COMMON_EXECUTION_STOP_OPTIONS)}},
}
add_common_options_info(COMMON_EXECUTION_STOP_OPTIONS_INFO)
