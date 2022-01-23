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

    def __init__(self, add_newline: bool = False):
        """

        Parameters
        ----------
        add_newline : bool
            If it is True, it will add a new line at the end of each echo operation. Otherwise it will always print
            into same line when echo is called.
        """
        self._add_newline = add_newline

    def consume(self, event: CWLogEvent):
        click.echo(event.message, nl=self._add_newline)
