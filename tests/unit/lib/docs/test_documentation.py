from unittest import TestCase
from unittest.mock import Mock, patch, mock_open

from samcli.lib.docs.documentation import Documentation, LANDING_PAGE


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

    @patch("samcli.lib.docs.documentation.Documentation.load")
    def test_get_docs_link_for_command(self, mock_load):
        mock_load.return_value = {"command": "link"}
        mock_browser = Mock()
        documentation = Documentation(browser=mock_browser, command="command")
        url = documentation.get_docs_link_for_command()
        self.assertEqual(url, "link")

    @patch("samcli.lib.docs.documentation.Documentation.load")
    def test_get_default_docs_link_for_command(self, mock_load):
        mock_load.return_value = {"command": "link"}
        mock_browser = Mock()
        documentation = Documentation(browser=mock_browser, command="command-invalid")
        url = documentation.get_docs_link_for_command()
        self.assertEqual(url, LANDING_PAGE)

    @patch("samcli.lib.docs.documentation.json")
    def test_load(self, mock_json):
        mock_file = Mock()
        mock_browser = Mock()
        documentation = Documentation(browser=mock_browser, command="command")
        with patch("builtins.open", mock_open()) as mock_open_func:
            documentation.load()
        mock_open_func.assert_called_once()
        mock_json.load.assert_called_once()
