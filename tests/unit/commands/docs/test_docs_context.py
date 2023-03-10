from unittest import TestCase
from unittest.mock import patch, Mock

from samcli.commands.docs.docs_context import DocsContext, ERROR_MESSAGE, SUCCESS_MESSAGE
from samcli.lib.docs.browser_configuration import BrowserConfigurationError


class TestDocsContext(TestCase):
    def test_delete_context_enter(self):
        with DocsContext() as docs_context:
            self.assertIsInstance(docs_context, DocsContext)

    @patch("samcli.commands.docs.docs_context.echo")
    @patch("samcli.commands.docs.docs_context.BrowserConfiguration")
    @patch("samcli.commands.docs.docs_context.Documentation")
    def test_run_command(self, mock_documentation, mock_browser_config, mock_echo):
        mock_browser = Mock()
        mock_documentation_object = Mock()
        mock_browser_config.return_value = mock_browser
        mock_documentation.return_value = mock_documentation_object
        with DocsContext() as docs_context:
            docs_context.run()
            mock_browser_config.assert_called_once()
            mock_documentation.assert_called_once_with(browser=mock_browser, url=DocsContext.URL)
            mock_documentation_object.open_docs.assert_called_once()
            mock_echo.assert_called_once_with(SUCCESS_MESSAGE)

    @patch("samcli.commands.docs.docs_context.echo")
    @patch("samcli.commands.docs.docs_context.BrowserConfiguration")
    @patch("samcli.commands.docs.docs_context.Documentation")
    def test_run_command_browser_exception(self, mock_documentation, mock_browser_config, mock_echo):
        mock_browser = Mock()
        mock_documentation_object = Mock()
        mock_documentation_object.open_docs.side_effect = BrowserConfigurationError
        mock_browser_config.return_value = mock_browser
        mock_documentation.return_value = mock_documentation_object
        with DocsContext() as docs_context:
            docs_context.run()
            mock_echo.assert_called_once_with(ERROR_MESSAGE.format(URL=DocsContext.URL))
