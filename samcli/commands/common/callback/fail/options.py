"""
Shared options for callback fail commands
"""

from typing import Dict, List

# Common options between local and remote callback fail commands
COMMON_CALLBACK_FAIL_OPTIONS: List[str] = ["error_data", "stack_trace", "error_type", "error_message"]

# Common options info
COMMON_CALLBACK_FAIL_OPTIONS_INFO: Dict[str, Dict] = {
    "Callback Options": {"option_names": {opt: {"rank": idx} for idx, opt in enumerate(COMMON_CALLBACK_FAIL_OPTIONS)}}
}
