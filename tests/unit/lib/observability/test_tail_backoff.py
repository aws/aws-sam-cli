from unittest import TestCase
from unittest.mock import Mock, call, patch

from botocore.exceptions import ClientError
from parameterized import parameterized

from samcli.lib.observability.cw_logs.cw_log_puller import CWLogPuller
from samcli.lib.observability.xray_traces.xray_event_puller import XRayTracePuller

PULLERS = [
    (
        "cloudwatch",
        lambda **kwargs: CWLogPuller(Mock(), Mock(), "log-group", **kwargs),
        "samcli.lib.observability.cw_logs.cw_log_puller",
    ),
    (
        "xray",
        lambda **kwargs: XRayTracePuller(Mock(), Mock(), **kwargs),
        "samcli.lib.observability.xray_traces.xray_event_puller",
    ),
]


class TestTailBackoff(TestCase):
    @parameterized.expand(PULLERS)
    def test_sustained_throttling_is_bounded(self, name, factory, module):
        puller = factory(max_retries=8)
        throttled = ClientError({"Error": {"Code": "ThrottlingException"}}, "operation")

        with patch.object(puller, "load_time_period", side_effect=throttled) as load, patch(
            module + ".time.sleep"
        ) as sleep:
            puller.tail()

        self.assertEqual(load.call_count, 8)
        self.assertEqual(sleep.call_args_list, [call(delay) for delay in [2, 4, 8, 16, 32, 60, 60, 60]])

    @parameterized.expand(
        [(name, factory, module, interval) for name, factory, module in PULLERS for interval in [1, 5, 90]]
    )
    def test_successful_poll_restores_configured_interval(self, name, factory, module, interval):
        puller = factory(max_retries=6, poll_interval=interval)
        throttled = ClientError({"Error": {"Code": "ThrottlingException"}}, "operation")
        responses = [throttled, throttled, None, throttled, None, None]
        expected = {
            1: [2, 4, 1, 2, 1, 1],
            5: [10, 20, 5, 10, 5, 5],
            90: [90, 90, 90, 90, 90, 90],
        }

        with patch.object(puller, "load_time_period", side_effect=responses) as load, patch(
            module + ".time.sleep"
        ) as sleep:
            puller.tail()

        self.assertEqual(load.call_count, 6)
        self.assertEqual(sleep.call_args_list, [call(delay) for delay in expected[interval]])
