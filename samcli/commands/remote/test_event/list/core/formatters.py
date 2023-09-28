"""
List Test Events Command Formatter.
"""
from samcli.commands.remote.test_event.core.formatters import RemoteTestEventCommandHelpTextFormatter
from samcli.commands.remote.test_event.list.core.options import ALL_OPTIONS


class RemoteTestEventListCommandHelpTextFormatter(RemoteTestEventCommandHelpTextFormatter):
    def __init__(self, *args, **kwargs):
        self.ALL_OPTIONS = ALL_OPTIONS
        super().__init__(*args, **kwargs)
