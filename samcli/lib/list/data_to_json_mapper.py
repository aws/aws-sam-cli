"""
Implementation of the data to json mapper
"""

import json
from typing import Dict

from samcli.lib.list.list_interfaces import Mapper


class DataToJsonMapper(Mapper):
    def map(self, data: Dict[str, str]) -> str:
        output = json.dumps(data, indent=2)
        return output
