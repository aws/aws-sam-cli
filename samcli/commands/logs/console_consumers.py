"""
Consumers that will print out events to console
"""

import click

from samcli.lib.observability.cw_logs.cw_log_event import CWLogEvent
from samcli.lib.observability.observability_info_puller import ObservabilityEventConsumer


class CWConsoleEventConsumer(ObservabilityEventConsumer[CWLogEvent]):
    """
    Consumer implementation that will consume given event as outputting into console
    """

    # pylint: disable=R0201
    def consume(self, event: CWLogEvent):
        click.echo(event.message, nl=False)
