import os
from datetime import datetime
from unittest import TestCase
from unittest.mock import patch, Mock, mock_open, call

from samcli.lib.observability.cw_logs.cw_log_consumers import CWFileEventConsumer
from samcli.lib.observability.cw_logs.cw_log_event import CWLogEvent


class TestCWFileEventConsumer(TestCase):
    @patch("samcli.lib.observability.cw_logs.cw_log_consumers.uuid")
    @patch("samcli.lib.observability.cw_logs.cw_log_consumers.time")
    def test_generated_file_name(self, patched_time, patched_uuid):
        given_time = Mock()
        patched_time.time.return_value = given_time

        given_uuid = Mock()
        patched_uuid.uuid4.return_value = given_uuid

        given_output_dir = "output_dir"
        file_consumer = CWFileEventConsumer(given_output_dir)

        self.assertEqual(file_consumer.file_name, os.path.join(given_output_dir, f"{given_uuid}-{given_time}.log"))

    @patch("samcli.lib.observability.cw_logs.cw_log_consumers.time")
    def test_given_file_name(self, patched_time):
        given_time = Mock()
        patched_time.time.return_value = given_time

        given_output_dir = "output_dir"
        given_file_prefix = "file_prefix"
        file_consumer = CWFileEventConsumer(given_output_dir, given_file_prefix)

        self.assertEqual(
            file_consumer.file_name, os.path.join(given_output_dir, f"{given_file_prefix}-{given_time}.log")
        )

    @patch("builtins.open", new_callable=mock_open)
    @patch("samcli.lib.observability.cw_logs.cw_log_consumers.json")
    def test_consume(self, patched_json, patched_file):
        given_output_dir = "output_dir"

        given_json_dumps = Mock()
        patched_json.dumps.return_value = given_json_dumps

        log_event = CWLogEvent("log_group", {"event": "dict"})

        file_consumer = CWFileEventConsumer(given_output_dir)
        file_consumer.consume(log_event)

        patched_json.dumps.assert_called_with(log_event.event)
        patched_file.assert_has_calls(
            [
                call(file_consumer.file_name, "a+"),
                call().write(f"{given_json_dumps}\n"),
            ],
            any_order=True,
        )
