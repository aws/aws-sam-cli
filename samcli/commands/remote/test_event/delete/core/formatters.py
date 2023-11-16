"""
Delete Test Event Command Formatter.
"""

from samcli.commands.remote.test_event.core.formatters import RemoteTestEventCommandHelpTextFormatter
from samcli.commands.remote.test_event.delete.core.options import ALL_OPTIONS


class RemoteTestEventDeleteCommandHelpTextFormatter(RemoteTestEventCommandHelpTextFormatter):
    def __init__(self, *args, **kwargs):
        self.ALL_OPTIONS = ALL_OPTIONS
        super().__init__(*args, **kwargs)
