"""
Implementation of the resources to table mapper
"""
from typing import Dict, Any
from collections import OrderedDict
from samcli.lib.list.list_interfaces import Mapper


class ResourcesToTableMapper(Mapper):
    def map(self, data: list) -> Dict[Any, Any]:
        entry_list = []
        for resource in data:
            entry_list.append(
                [
                    resource.get("LogicalResourceId", "-"),
                    resource.get("PhysicalResourceId", "-"),
                ]
            )
        table_data = {
            "format_string": "{Logical ID:<{0}} {Physical ID:<{1}}",
            "format_args": OrderedDict(
                {
                    "Logical ID": "Logical ID",
                    "Physical ID": "Physical ID",
                }
            ),
            "table_name": "Resources",
            "data": entry_list,
        }
        return table_data
