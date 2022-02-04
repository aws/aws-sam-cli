from unittest import TestCase
from unittest.mock import patch, call, Mock

from parameterized import parameterized

from samcli.commands.traces.command import do_cli
from samcli.lib.observability.util import OutputOption


class TestTracesCommand(TestCase):
    def setUp(self):
        self.region = "region"

    @parameterized.expand(
        [
            (None, None, None, False, "text"),
            (["trace_id1", "trace_id2"], None, None, False, "text"),
            (None, "start_time", None, False, "text"),
            (None, "start_time", "end_time", False, "text"),
            (None, None, None, True, "text"),
            (None, None, None, True, "json"),
        ]
    )
    @patch("samcli.commands.logs.logs_context.parse_time")
    @patch("samcli.lib.utils.boto_utils.get_boto_config_with_user_agent")
    @patch("boto3.client")
    @patch("samcli.commands.traces.traces_puller_factory.generate_trace_puller")
    def test_traces_command(
        self,
        trace_ids,
        start_time,
        end_time,
        tail,
        output,
        patched_generate_puller,
        patched_boto3,
        patched_get_boto_config_with_user_agent,
        patched_parse_time,
    ):
        given_start_time = Mock()
        given_end_time = Mock()
        patched_parse_time.side_effect = [given_start_time, given_end_time]

        given_boto_config = Mock()
        patched_get_boto_config_with_user_agent.return_value = given_boto_config

        given_xray_client = Mock()
        patched_boto3.return_value = given_xray_client

        given_puller = Mock()
        patched_generate_puller.return_value = given_puller

        do_cli(trace_ids, start_time, end_time, tail, output, self.region)

        patched_parse_time.assert_has_calls(
            [
                call(start_time, "start-time"),
                call(end_time, "end-time"),
            ]
        )
        patched_get_boto_config_with_user_agent.assert_called_with(region_name=self.region)
        patched_boto3.assert_called_with("xray", config=given_boto_config)
        patched_generate_puller.assert_called_with(given_xray_client, OutputOption(output))

        if trace_ids:
            given_puller.load_events.assert_called_with(trace_ids)
        elif tail:
            given_puller.tail.assert_called_with(given_start_time)
        else:
            given_puller.load_time_period.assert_called_with(given_start_time, given_end_time)
