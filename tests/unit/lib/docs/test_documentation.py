from unittest import TestCase
from unittest.mock import Mock

from samcli.lib.docs.documentation import Documentation


class TestDocumentation(TestCase):
    def test_open_docs(self):
        url = "https://sam-is-the-best.com"
        mock_browser = Mock()
        documentation = Documentation(browser=mock_browser, url=url)
        documentation.open_docs()
        mock_browser.launch.assert_called_with(url)
