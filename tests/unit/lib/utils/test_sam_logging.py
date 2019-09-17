from unittest import TestCase
from mock import patch, Mock

from samcli.lib.utils.sam_logging import SamCliLogger


class TestSamCliLogger(TestCase):
    @patch("samcli.lib.utils.sam_logging.logging")
    def test_configure_samcli_logger(self, logging_patch):
        formatter_mock = Mock()
        logger_mock = Mock()
        logging_patch.DEBUG = 2

        stream_handler_mock = Mock()
        logging_patch.StreamHandler.return_value = stream_handler_mock

        SamCliLogger.configure_logger(logger_mock, formatter_mock, level=1)

        self.assertFalse(logger_mock.propagate)

        logger_mock.setLevel.assert_called_once_with(1)
        logger_mock.addHandler.assert_called_once_with(stream_handler_mock)
        stream_handler_mock.setLevel.assert_called_once_with(2)
        stream_handler_mock.setFormatter.assert_called_once_with(formatter_mock)
