"""
Implementation of the resources to table mapper
"""
from collections import OrderedDict
from typing import Any, Dict

from samcli.lib.list.list_interfaces import Mapper


class ResourcesToTableMapper(Mapper):
    """
    Mapper class for mapping resources data for table output
    """

    def map(self, data: list) -> Dict[Any, Any]:
        """
        Maps data to the format needed for consumption by the table consumer

        Parameters
        ----------
        data: list
            List of dictionaries containing the entries of the resources data

        Returns
        -------
        table_data: Dict[Any, Any]
            Dictionary containing the information and data needed for the table
            consumer to output the data in table format
        """
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
