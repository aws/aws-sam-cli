import os

import sys
from unittest import TestCase

from parameterized import parameterized
from unittest.mock import patch, Mock

from samcli.lib.utils.subprocess_utils import (
    default_loading_pattern,
    invoke_subprocess_with_loading_pattern,
    LoadingPatternError,
)


class TestSubprocessUtils(TestCase):
    @parameterized.expand([(0,), (1,), (2,), (3,), (5,), (10,)])
    @patch("samcli.lib.utils.subprocess_utils.Popen")
    def test_loader_successfully_prints_pattern_n_times(self, pattern_count, patched_Popen):
        expected_output = "expected_output"
        mock_stream_writer = Mock()
        mock_process = Mock()
        mock_process.wait.return_value = 0
        mock_process.stdout.read.return_value = expected_output
        mock_pattern = Mock()
        mock_process.poll.side_effect = ([None] * pattern_count) + [0]
        patched_Popen.return_value.__enter__.return_value = mock_process
        actual_output = invoke_subprocess_with_loading_pattern({"args": ["ls"]}, mock_pattern, mock_stream_writer)
        mock_stream_writer.write.assert_called_once_with(os.linesep)
        mock_stream_writer.flush.assert_called_once_with()
        patched_Popen.assert_called_once_with(args=["ls"])
        self.assertEqual(mock_pattern.call_count, pattern_count)
        self.assertEqual(actual_output, expected_output)

    @patch("samcli.lib.utils.subprocess_utils.Popen")
    def test_loader_raises_exception_non_zero_exit_code(self, patched_Popen):
        standard_error = "an error has occurred"
        mock_stream_writer = Mock()
        mock_process = Mock()
        mock_process.returncode = 1
        mock_process.stderr.read.return_value = standard_error
        mock_pattern = Mock()
        mock_process.poll.return_value = 1
        patched_Popen.return_value.__enter__.return_value = mock_process
        with self.assertRaises(LoadingPatternError) as ex:
            invoke_subprocess_with_loading_pattern({"args": ["ls"]}, mock_pattern, mock_stream_writer)
        self.assertIn(standard_error, ex.exception.message)
        mock_stream_writer.write.assert_called_once_with("\n")
        mock_stream_writer.flush.assert_called_once_with()

    @patch("samcli.lib.utils.subprocess_utils.Popen")
    def test_loader_raises_exception_bad_process(self, patched_Popen):
        standard_error = "an error has occurred"
        mock_stream_writer = Mock()
        mock_process = Mock()
        mock_process.returncode = 1
        mock_process.stderr.read.return_value = standard_error
        mock_pattern = Mock()
        mock_process.poll.return_value = 1
        patched_Popen.return_value.__enter__.side_effect = ValueError(standard_error)
        with self.assertRaises(LoadingPatternError) as ex:
            invoke_subprocess_with_loading_pattern({"args": ["ls"]}, mock_pattern, mock_stream_writer)
        self.assertIn(standard_error, ex.exception.message)
        mock_stream_writer.write.assern_not_called()
        mock_stream_writer.flush.assern_not_called()

    @patch("samcli.lib.utils.subprocess_utils.StreamWriter")
    def test_default_pattern_default_stream_writer(self, patched_stream_writer):
        stream_writer_mock = Mock()
        patched_stream_writer.return_value = stream_writer_mock
        default_loading_pattern(loading_pattern_rate=0.01)
        patched_stream_writer.assert_called_once_with(sys.stderr)
        stream_writer_mock.write.assert_called_once_with(".")
        stream_writer_mock.flush.assert_called_once_with()

    @patch("samcli.lib.utils.subprocess_utils.StreamWriter")
    def test_default_pattern(self, patched_stream_writer):
        stream_writer_mock = Mock()
        default_loading_pattern(stream_writer_mock, 0.01)
        patched_stream_writer.assert_not_called()
        stream_writer_mock.write.assert_called_once_with(".")
        stream_writer_mock.flush.assert_called_once_with()
