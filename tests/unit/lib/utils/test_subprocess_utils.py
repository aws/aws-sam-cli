from subprocess import DEVNULL

import logging
from io import StringIO

import os

import sys
from unittest import TestCase

from parameterized import parameterized
from unittest.mock import patch, Mock, call, ANY

from samcli.lib.utils.subprocess_utils import (
    default_loading_pattern,
    invoke_subprocess_with_loading_pattern,
    LoadingPatternError,
    _check_and_process_bytes,
    _check_and_convert_stream_to_string,
)


class TestSubprocessUtils(TestCase):
    @patch("samcli.lib.utils.subprocess_utils._check_and_convert_stream_to_string")
    @patch("samcli.lib.utils.subprocess_utils._check_and_process_bytes")
    @patch("samcli.lib.utils.subprocess_utils.LOG")
    @patch("samcli.lib.utils.subprocess_utils.Popen")
    def test_loader_stream_logs_when_debug_level(
        self, patched_Popen, patched_log, patched_check_and_process_byes, patched_check_and_convert_stream_to_string
    ):
        expected_output = f"Line 1{os.linesep}Line 2"
        patched_log.getEffectiveLevel.return_value = logging.DEBUG
        mock_process = Mock()
        mock_process.wait.return_value = 0
        mock_process.stdout = StringIO(expected_output)
        patched_Popen.return_value.__enter__.return_value = mock_process
        mock_pattern = Mock()
        mock_stream_writer = Mock()
        patched_check_and_process_byes.side_effect = [f"Line 1{os.linesep}", "Line 2"]
        actual_output = invoke_subprocess_with_loading_pattern({"args": ["ls"]}, mock_pattern, mock_stream_writer)
        patched_check_and_process_byes.assert_has_calls([call(f"Line 1{os.linesep}"), call("Line 2")])
        mock_pattern.assert_not_called()
        self.assertEqual(patched_check_and_convert_stream_to_string.call_count, 1)
        self.assertEqual(actual_output, expected_output)

    @patch("samcli.lib.utils.subprocess_utils._check_and_convert_stream_to_string")
    @patch("samcli.lib.utils.subprocess_utils._check_and_process_bytes")
    @patch("samcli.lib.utils.subprocess_utils.LOG")
    @patch("samcli.lib.utils.subprocess_utils.Popen")
    def test_loader_stream_uses_passed_in_stdout(
        self, patched_Popen, patched_log, patched_check_and_process_byes, patched_check_and_convert_stream_to_string
    ):
        expected_output = f"Line 1{os.linesep}Line 2"
        mock_pattern = Mock()
        mock_stream_writer = Mock()
        mock_process = Mock()
        mock_process.stdout = StringIO(expected_output)
        mock_process.wait.return_value = 0
        patched_Popen.return_value.__enter__.return_value = mock_process
        patched_log.getEffectiveLevel.return_value = logging.INFO
        invoke_subprocess_with_loading_pattern({"args": ["ls"], "stdout": DEVNULL}, mock_pattern, mock_stream_writer)
        patched_Popen.assert_called_once_with(args=["ls"], stdout=DEVNULL)

    @patch("samcli.lib.utils.subprocess_utils.Popen")
    def test_loader_raises_exception_non_zero_exit_code(self, patched_Popen):
        standard_error = "an error has occurred"
        mock_stream_writer = Mock()
        mock_process = Mock()
        mock_process.returncode = 1
        mock_process.stdout = None
        mock_process.stderr.read.return_value = standard_error
        mock_pattern = Mock()
        patched_Popen.return_value.__enter__.return_value = mock_process
        with self.assertRaises(LoadingPatternError) as ex:
            invoke_subprocess_with_loading_pattern({"args": ["ls"]}, mock_pattern, mock_stream_writer)
        self.assertIn(standard_error, ex.exception.message)
        mock_stream_writer.write.assert_called_once_with(os.linesep)
        mock_stream_writer.flush.assert_called_once_with()

    @patch("samcli.lib.utils.subprocess_utils.Popen")
    def test_loader_raises_exception_bad_process(self, patched_Popen):
        standard_error = "an error has occurred"
        mock_stream_writer = Mock()
        mock_process = Mock()
        mock_process.returncode = 1
        mock_process.stdout = None
        mock_process.stderr.read.return_value = standard_error
        mock_pattern = Mock()
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

    @parameterized.expand([("hello".encode("utf-8"), "hello"), ("hello", "hello")])
    def test_check_and_process_bytes(self, sample_input, expected_output):
        output = _check_and_process_bytes(sample_input)
        self.assertIsInstance(output, str)
        self.assertEqual(output, expected_output)

    @patch("samcli.lib.utils.subprocess_utils._check_and_process_bytes")
    def test_check_and_convert_stream_to_string(self, patched_check_and_process_bytes):
        sample_input_output = "hello"
        sample_stream = StringIO(sample_input_output)
        patched_check_and_process_bytes.return_value = sample_input_output
        output = _check_and_convert_stream_to_string(sample_stream)
        patched_check_and_process_bytes.assert_called_once_with(sample_input_output)
        self.assertEqual(output, sample_input_output)

    @patch("samcli.lib.utils.subprocess_utils._check_and_process_bytes")
    def test_check_and_convert_stream_to_string_none_stream(self, patched_check_and_process_bytes):
        sample_input_output = ""
        sample_stream = None
        patched_check_and_process_bytes.return_value = sample_input_output
        output = _check_and_convert_stream_to_string(sample_stream)
        patched_check_and_process_bytes.assert_not_called()
        self.assertEqual(output, sample_input_output)
