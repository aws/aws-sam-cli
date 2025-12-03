"""
Shared options for callback succeed commands
"""

from typing import Dict, List

# Common options between local and remote callback succeed commands
COMMON_CALLBACK_SUCCEED_OPTIONS: List[str] = ["result"]

# Common options info
COMMON_CALLBACK_SUCCEED_OPTIONS_INFO: Dict[str, Dict] = {
    "Callback Options": {
        "option_names": {opt: {"rank": idx} for idx, opt in enumerate(COMMON_CALLBACK_SUCCEED_OPTIONS)}
    }
}
