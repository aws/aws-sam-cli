"""
Implementation of the stack output to table mapper
"""
from samcli.lib.list.list_interfaces import Mapper
from samcli.views.concrete_views.rich_table import RichTable


class StackOutputToTableMapper(Mapper):
    def map(self, data: list) -> RichTable:
        output = RichTable(title="Stack Outputs", table_options={"show_lines": True})
        output.add_column("OutputKey", {"justify": "center", "no_wrap": True})
        output.add_column("OutputValue", {"justify": "center", "no_wrap": True})
        output.add_column("Description", {"justify": "center", "no_wrap": True})
        for stack_output in data:
            output.add_row([stack_output["OutputKey"], stack_output["OutputValue"], stack_output["Description"]])
        return output
