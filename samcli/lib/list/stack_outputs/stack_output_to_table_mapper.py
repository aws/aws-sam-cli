"""
Implementation of the stack output to table mapper
"""
from typing import Dict, Any
from collections import OrderedDict
from samcli.lib.list.list_interfaces import Mapper


class StackOutputToTableMapper(Mapper):
    def map(self, data: list) -> Dict[Any, Any]:
        entry_list = []
        for stack_output in data:
            entry_list.append(
                [
                    stack_output.get("OutputKey", "-"),
                    stack_output.get("OutputValue", "-"),
                    stack_output.get("Description", "-"),
                ]
            )
        table_data = {
            "format_string": "{OutputKey:<{0}} {OutputValue:<{1}} {Description:<{2}}",
            "format_args": OrderedDict(
                {"OutputKey": "OutputKey", "OutputValue": "OutputValue", "Description": "Description"}
            ),
            "table_name": "Stack Outputs",
            "data": entry_list,
        }
        return table_data
