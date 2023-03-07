"""
The json consumer for 'sam list'
"""
import click

from samcli.lib.list.list_interfaces import ListInfoPullerConsumer


class StringConsumerJsonOutput(ListInfoPullerConsumer):
    """
    Consumes string data and outputs it in json format
    """

    def consume(self, data: str) -> None:
        click.echo(data)
