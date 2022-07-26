"""
The table consumer for 'sam list'
"""
from samcli.lib.list.list_interfaces import ListInfoPullerConsumer
from samcli.views.concrete_views.rich_table import RichTable


class StringConsumerTableOutput(ListInfoPullerConsumer):
    """
    Consumes a Rich table and outputs it in table format
    """

    def consume(self, data: RichTable) -> None:
        data.print()
