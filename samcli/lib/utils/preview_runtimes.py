"""
Keeps list of preview runtimes, which can be used with sam build or sam local commands.
But deployment of them would probably fail until their GA date
"""
from typing import Set

PREVIEW_RUNTIMES: Set[str] = set()
