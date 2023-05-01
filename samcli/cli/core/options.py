"""
Base Command Options related Data Structures for formatting.
"""
from typing import Dict, List

# The ordering of the option lists matter, they are the order in which options will be displayed.

BETA_OPTIONS: List[str] = ["beta_features"]
OTHER_OPTIONS: List[str] = ["debug", "help"]

ALL_COMMON_OPTIONS: List[str] = BETA_OPTIONS + OTHER_OPTIONS

OPTIONS_INFO: Dict[str, Dict] = {
    "Beta Options": {"option_names": {opt: {"rank": idx} for idx, opt in enumerate(BETA_OPTIONS)}},
    "Other Options": {"option_names": {opt: {"rank": idx} for idx, opt in enumerate(OTHER_OPTIONS)}},
}


def add_common_options_info(formatting_options: Dict) -> None:
    """Add global options to"""
    # Append global options to the end if they are not
    for option_heading, options in OPTIONS_INFO.items():
        formatting_options[option_heading] = options
