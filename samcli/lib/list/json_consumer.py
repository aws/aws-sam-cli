"""
The json consumer for 'sam list'
"""
import click
from samcli.lib.list.consumer import Consumer


class JsonConsumer(Consumer):
    def consume(self, data: str) -> None:
        click.echo(data)
