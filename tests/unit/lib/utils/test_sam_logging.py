from unittest import TestCase
from unittest.mock import patch, Mock

from samcli.lib.utils.sam_logging import SamCliLogger


class TestSamCliLogger(TestCase):
    @patch("samcli.lib.utils.sam_logging.logging")
    def test_configure_samcli_logger(self, logging_patch):
        formatter_mock = Mock()
        logger_mock = Mock()
        logger_mock.handlers = []
        logging_patch.DEBUG = 2

        stream_handler_mock = Mock()
        logging_patch.StreamHandler.return_value = stream_handler_mock

        SamCliLogger.configure_logger(logger_mock, formatter_mock, level=1)

        self.assertFalse(logger_mock.propagate)

        logger_mock.setLevel.assert_called_once_with(1)
        logger_mock.addHandler.assert_called_once_with(stream_handler_mock)
        stream_handler_mock.setLevel.assert_called_once_with(2)
        stream_handler_mock.setFormatter.assert_called_once_with(formatter_mock)

    @patch("samcli.lib.utils.sam_logging.logging")
    @patch("samcli.lib.utils.sam_logging.sys")
    @patch("samcli.lib.utils.sam_logging.os")
    @patch("samcli.lib.utils.sam_logging.RichHandler")
    def test_configure_samcli_logger_mock_terminal(self, mock_rich_handler, mock_os, mock_sys, logging_patch):
        mock_sys.stderr.isatty = Mock(return_value=True)
        mock_os.getenv = Mock(return_value=None)
        formatter_mock = Mock()
        logger_mock = Mock()
        logger_mock.handlers = []
        logging_patch.DEBUG = 2

        SamCliLogger.configure_logger(logger_mock, formatter_mock, level=1)

        self.assertFalse(logger_mock.propagate)

        logger_mock.setLevel.assert_called_once_with(1)
        logger_mock.addHandler.assert_called_once_with(mock_rich_handler())
        mock_rich_handler().setLevel.assert_called_once_with(2)
        mock_rich_handler().setFormatter.assert_called_once_with(formatter_mock)

    @patch("samcli.lib.utils.sam_logging.logging")
    @patch("samcli.lib.utils.sam_logging.sys")
    @patch("samcli.lib.utils.sam_logging.os")
    @patch("samcli.lib.utils.sam_logging.RichHandler")
    def test_configure_samcli_logger_mock_terminal_opt_out(self, mock_rich_handler, mock_os, mock_sys, logging_patch):
        mock_sys.stderr.isatty = Mock(return_value=True)
        mock_os.getenv = Mock(return_value="1")
        formatter_mock = Mock()
        logger_mock = Mock()
        logger_mock.handlers = []
        logging_patch.DEBUG = 2
        stream_handler_mock = Mock()
        logging_patch.StreamHandler.return_value = stream_handler_mock

        SamCliLogger.configure_logger(logger_mock, formatter_mock, level=1)
        self.assertFalse(logger_mock.propagate)

        logger_mock.setLevel.assert_called_once_with(1)
        logger_mock.addHandler.assert_called_once_with(stream_handler_mock)
        stream_handler_mock.setLevel.assert_called_once_with(2)
        stream_handler_mock.setFormatter.assert_called_once_with(formatter_mock)
        mock_rich_handler().assert_not_called()

    @patch("samcli.lib.utils.sam_logging.logging")
    def test_configure_samcli_logger_null_logger(self, logging_patch):
        logger_mock = Mock()

        SamCliLogger.configure_null_logger(logger_mock)

        self.assertFalse(logger_mock.propagate)

        logger_mock.addHandler.assert_called_once_with(logging_patch.NullHandler())
