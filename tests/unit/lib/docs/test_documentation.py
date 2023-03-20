from unittest import TestCase
from unittest.mock import Mock

from samcli.lib.docs.documentation import Documentation


class TestDocumentation(TestCase):
    def test_open_docs(self):
        url = (
            "https://docs.aws.amazon.com/serverless-application-model/"
            "latest/developerguide/sam-cli-command-reference-sam-list.html"
        )
        mock_browser = Mock()
        documentation = Documentation(browser=mock_browser, command="list")
        documentation.open_docs()
        mock_browser.launch.assert_called_with(url)
