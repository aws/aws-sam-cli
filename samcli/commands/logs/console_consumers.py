"""
Consumers that will print out events to console
"""
from typing import Any

import click

from samcli.lib.observability.observability_info_puller import ObservabilityEventConsumer


class CWConsoleEventConsumer(ObservabilityEventConsumer):
    """
    Consumer implementation that will consume given event as outputting into console
    """

    def consume(self, event: Any):
        click.echo(event, nl=False)
