"""
Shared options for execution get commands
"""

from typing import Dict, List

from samcli.cli.core.options import add_common_options_info

# Common options between local and remote execution get commands
COMMON_EXECUTION_GET_FORMATTING_OPTIONS: List[str] = ["format"]

# Common options info with common options included
COMMON_EXECUTION_GET_FORMATTING_OPTIONS_INFO: Dict[str, Dict] = {
    "Formatting Options": {
        "option_names": {opt: {"rank": idx} for idx, opt in enumerate(COMMON_EXECUTION_GET_FORMATTING_OPTIONS)}
    },
}
add_common_options_info(COMMON_EXECUTION_GET_FORMATTING_OPTIONS_INFO)
