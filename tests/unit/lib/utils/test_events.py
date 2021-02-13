"""
Tests Utils events
"""

from unittest import TestCase
from unittest.mock import patch, Mock

from parameterized import parameterized, param

from samcli.lib.utils.events import get_event

STDIN_FILE_NAME = "-"


class TestGetEvent(TestCase):
    @parameterized.expand([param(STDIN_FILE_NAME), param("somefile")])
    @patch("samcli.lib.utils.events.click")
    def test_must_work_with_stdin(self, filename, click_mock):
        event_data = "some data"

        # Mock file pointer
        fp_mock = Mock()

        # Mock the context manager
        click_mock.open_file.return_value.__enter__.return_value = fp_mock
        fp_mock.read.return_value = event_data

        result = get_event(filename)

        self.assertEqual(result, event_data)
        fp_mock.read.assert_called_with()
