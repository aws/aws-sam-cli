from typing import Callable
from unittest import TestCase
from unittest.mock import Mock, call, patch

from botocore.exceptions import ClientError
from botocore.session import Session
from botocore.stub import Stubber
from parameterized import parameterized

from samcli.lib.observability.cw_logs.cw_log_puller import CWLogPuller
from samcli.lib.observability.observability_info_puller import ObservabilityPuller
from samcli.lib.observability.xray_traces.xray_event_puller import AbstractXRayPuller, XRayTracePuller
from samcli.lib.observability.xray_traces.xray_service_graph_event_puller import XRayServiceGraphPuller

PULLERS = [
    (
        "cloudwatch",
        lambda **kwargs: CWLogPuller(Mock(), Mock(), "log-group", **kwargs),
        "samcli.lib.observability.cw_logs.cw_log_puller",
        "ThrottlingException",
    ),
    (
        "xray_traces",
        lambda **kwargs: XRayTracePuller(Mock(), Mock(), **kwargs),
        "samcli.lib.observability.xray_traces.xray_event_puller",
        "ThrottledException",
    ),
    (
        "xray_service_graph",
        lambda **kwargs: XRayServiceGraphPuller(Mock(), Mock(), **kwargs),
        "samcli.lib.observability.xray_traces.xray_event_puller",
        "ThrottledException",
    ),
]


class TestTailErrors(TestCase):
    @parameterized.expand(PULLERS)
    def test_access_denied_after_throttle_does_not_sleep_again(
        self, name: str, factory: Callable[..., ObservabilityPuller], module: str, throttle_code: str
    ) -> None:
        puller = factory(max_retries=3)
        throttled = ClientError({"Error": {"Code": throttle_code}}, "operation")
        denied = ClientError({"Error": {"Code": "AccessDeniedException"}}, "operation")

        with (
            patch.object(puller, "load_time_period", side_effect=[throttled, denied]) as load,
            patch(module + ".time.sleep") as sleep,
        ):
            with self.assertRaises(ClientError) as raised:
                puller.tail()

        self.assertIs(raised.exception, denied)
        self.assertEqual(load.call_count, 2)
        self.assertEqual(sleep.call_args_list, [call(2)])

    @parameterized.expand(
        [
            ("get_trace_summaries", XRayTracePuller),
            ("batch_get_traces", XRayTracePuller),
            ("get_service_graph", XRayServiceGraphPuller),
        ]
    )
    def test_xray_api_throttle_backs_off(self, operation: str, puller_class: Callable[..., AbstractXRayPuller]) -> None:
        client = Session().create_client(
            "xray", region_name="us-east-1", aws_access_key_id="testing", aws_secret_access_key="testing"
        )
        consumer = Mock()
        puller = puller_class(client, consumer, max_retries=1)

        with (
            Stubber(client) as stubber,
            patch("samcli.lib.observability.xray_traces.xray_event_puller.time.sleep") as sleep,
        ):
            if operation == "batch_get_traces":
                stubber.add_response(
                    "get_trace_summaries", {"TraceSummaries": [{"Id": "1-67891233-abcdef012345678912345678"}]}
                )
            stubber.add_client_error(operation, service_error_code="ThrottledException", http_status_code=429)

            puller.tail()

            stubber.assert_no_pending_responses()

        sleep.assert_called_once_with(2)
        consumer.consume.assert_not_called()
