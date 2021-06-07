import os
from unittest import TestCase
from unittest.mock import patch, mock_open, call, Mock

from samcli.lib.observability.xray_traces.xray_event_consumers import XRayEventFileConsumer


class TestXRayEventFileConsumer(TestCase):
    @patch("samcli.lib.observability.xray_traces.xray_event_consumers.uuid")
    @patch("samcli.lib.observability.xray_traces.xray_event_consumers.time")
    def test_file_name(self, patched_time, patched_uuid):
        output_dir = "output_dir"

        patched_time.time.return_value = "time"
        patched_uuid.uuid4.return_value = "uuid"

        file_consumer = XRayEventFileConsumer(output_dir)

        self.assertEqual(file_consumer.file_name, os.path.join(output_dir, f"uuid-time.json"))

    @patch("samcli.lib.observability.xray_traces.xray_event_consumers.json")
    @patch("builtins.open", new_callable=mock_open)
    def test_consume(self, patched_open, patched_json):
        event = Mock()
        given_json_dumps = Mock()
        patched_json.dumps.return_value = given_json_dumps

        file_consumer = XRayEventFileConsumer("output_dir")
        file_consumer.consume(event)

        patched_json.dumps.assert_called_with(event.event)

        patched_open.assert_has_calls(
            [
                call(file_consumer.file_name, "a+"),
                call().write(f"{given_json_dumps}\n"),
            ],
            any_order=True,
        )
