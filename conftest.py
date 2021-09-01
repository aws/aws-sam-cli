import pytest
import datetime
import sys

from _pytest.terminal import TerminalReporter


class TimestampReporter(TerminalReporter):
    def __init__(self, config, file=None) -> None:
        super().__init__(config, file)

    def _locationline(self, nodeid, fspath, lineno, domain):
        line = super()._locationline(nodeid, fspath, lineno, domain)
        datetime_string = datetime.datetime.now().strftime("%H:%M:%S")
        return f"[{datetime_string}] {line}"


@pytest.mark.trylast
def pytest_configure(config) -> None:
    terminal_reporter_plugin = config.pluginmanager.get_plugin("terminalreporter")
    config.pluginmanager.unregister(terminal_reporter_plugin, "terminalreporter")
    config.pluginmanager.register(TimestampReporter(config, sys.stdout), "terminalreporter")
