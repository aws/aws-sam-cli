from unittest import TestCase
from unittest.mock import patch, Mock

from samcli.commands.docs.command_context import DocsCommandContext, ERROR_MESSAGE, SUCCESS_MESSAGE
from samcli.lib.docs.browser_configuration import BrowserConfigurationError


class TestDocsContext(TestCase):
    """"""
