from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.commands.docs.command import do_cli


class TestDocsCliCommand(TestCase):
    @patch("samcli.commands.docs.command.click")
    @patch("samcli.commands.docs.docs_context.DocsContext")
    def test_all_args(self, mock_docs_context, mock_docs_click):
        context_mock = Mock()
        mock_docs_context.return_value.__enter__.return_value = context_mock

        do_cli()

        mock_docs_context.assert_called_with()

        context_mock.run.assert_called_with()
        self.assertEqual(context_mock.run.call_count, 1)
