from unittest import TestCase
from unittest.mock import patch, Mock

from samcli.commands.docs.docs_context import DocsContext


class TestDocsContext(TestCase):
    def test_delete_context_enter(self):
        with DocsContext(
            config_file="samconfig.toml",
            config_env="default",
        ) as docs_context:
            self.assertIsInstance(docs_context, DocsContext)

    @patch("samcli.commands.docs.docs_context.BrowserConfiguration")
    @patch("samcli.commands.docs.docs_context.Documentation")
    def test_run_command(self, mock_documentation, mock_browser_config):
        mock_browser = Mock()
        mock_documentation_object = Mock()
        mock_browser_config.return_value = mock_browser
        mock_documentation.return_value = mock_documentation_object
        with DocsContext(
                config_file="samconfig.toml",
                config_env="default",
        ) as docs_context:
            docs_context.run()
            mock_browser_config.assert_called_once()
            mock_documentation.assert_called_once_with(browser=mock_browser, url=DocsContext.URL)
            mock_documentation_object.open_docs.assert_called_once()
