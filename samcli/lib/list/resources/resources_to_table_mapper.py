"""
Implementation of the resources to table mapper
"""
from samcli.lib.list.list_interfaces import Mapper
from samcli.views.concrete_views.rich_table import RichTable


class ResourcesToTableMapper(Mapper):
    def map(self, data: list) -> RichTable:
        output = RichTable(title="Resources", table_options={"show_lines": True})
        output.add_column("Logical ID", {"justify": "center", "no_wrap": True})
        output.add_column("Physical ID", {"justify": "center", "no_wrap": True})
        for resource in data:
            output.add_row([resource["LogicalResourceId"], resource["PhysicalResourceId"]])
        return output
