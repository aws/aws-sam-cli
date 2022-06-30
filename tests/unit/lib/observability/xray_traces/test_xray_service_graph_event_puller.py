import time
import uuid
from itertools import zip_longest
from unittest import TestCase
from unittest.mock import patch, mock_open, call, Mock, ANY

from botocore.exceptions import ClientError
from parameterized import parameterized

from samcli.lib.observability.xray_traces.xray_event_puller import XRayTracePuller
from samcli.lib.observability.xray_traces.xray_service_graph_event_puller import XRayServiceGraphPuller


class TestXRayServiceGraphPuller(TestCase):
    def setUp(self):
        self.xray_client = Mock()
        self.consumer = Mock()

        self.max_retries = 4
        self.xray_service_graph_puller = XRayServiceGraphPuller(self.xray_client, self.consumer, self.max_retries)

    @patch("samcli.lib.observability.xray_traces.xray_service_graph_event_puller.XRayServiceGraphEvent")
    @patch("samcli.lib.observability.xray_traces.xray_service_graph_event_puller.to_utc")
    @patch("samcli.lib.observability.xray_traces.xray_service_graph_event_puller.utc_to_timestamp")
    def test_load_time_period(self, patched_utc_to_timestamp, patched_to_utc, patched_xray_service_graph_event):
        given_paginator = Mock()
        self.xray_client.get_paginator.return_value = given_paginator

        given_services = [{"EndTime": "endtime", "Services": [{"id": 1}]}]
        given_paginator.paginate.return_value = given_services

        start_time = "start_time"
        end_time = "end_time"
        patched_utc_to_timestamp.return_value = 1
        self.xray_service_graph_puller.load_time_period(start_time, end_time)
        patched_utc_to_timestamp.assert_called()
        patched_to_utc.assert_called()
        given_paginator.paginate.assert_called_with(StartTime=start_time, EndTime=end_time)
        patched_xray_service_graph_event.assrt_called_with({"EndTime": "endtime", "Services": [{"id": 1}]})
        self.consumer.consume.assert_called()

    @patch("samcli.lib.observability.xray_traces.xray_service_graph_event_puller.XRayServiceGraphEvent")
    @patch("samcli.lib.observability.xray_traces.xray_service_graph_event_puller.to_utc")
    @patch("samcli.lib.observability.xray_traces.xray_service_graph_event_puller.utc_to_timestamp")
    def test_load_time_period_with_same_event_twice(
        self, patched_utc_to_timestamp, patched_to_utc, patched_xray_service_graph_event
    ):
        given_paginator = Mock()
        self.xray_client.get_paginator.return_value = given_paginator

        given_services = [{"EndTime": "endtime", "Services": [{"id": 1}]}]
        given_paginator.paginate.return_value = given_services

        start_time = "start_time"
        end_time = "end_time"
        patched_utc_to_timestamp.return_value = 1
        self.xray_service_graph_puller.load_time_period(start_time, end_time)
        # called with the same event twice
        self.xray_service_graph_puller.load_time_period(start_time, end_time)
        patched_utc_to_timestamp.assert_called()
        patched_to_utc.assert_called()
        given_paginator.paginate.assert_called_with(StartTime=start_time, EndTime=end_time)
        patched_xray_service_graph_event.assrt_called_with({"EndTime": "endtime", "Services": [{"id": 1}]})
        # consumer should only get called once
        self.consumer.consume.assert_called_once()

    @patch("samcli.lib.observability.xray_traces.xray_service_graph_event_puller.XRayServiceGraphEvent")
    def test_load_time_period_with_no_service(self, patched_xray_service_graph_event):
        given_paginator = Mock()
        self.xray_client.get_paginator.return_value = given_paginator

        given_services = [{"EndTime": "endtime", "Services": []}]
        given_paginator.paginate.return_value = given_services

        start_time = "start_time"
        end_time = "end_time"
        self.xray_service_graph_puller.load_time_period(start_time, end_time)
        patched_xray_service_graph_event.assert_not_called()
        self.consumer.consume.assert_not_called()

    @patch("samcli.lib.observability.xray_traces.xray_event_puller.time")
    @patch("samcli.lib.observability.xray_traces.xray_event_puller.to_timestamp")
    @patch("samcli.lib.observability.xray_traces.xray_event_puller.to_datetime")
    def test_tail_with_no_data(self, patched_to_datetime, patched_to_timestamp, patched_time):
        start_time = Mock()

        with patch.object(self.xray_service_graph_puller, "load_time_period") as patched_load_time_period:
            self.xray_service_graph_puller.tail(start_time)

            patched_to_timestamp.assert_called_with(start_time)

            patched_to_datetime.assert_has_calls(
                [call(self.xray_service_graph_puller.latest_event_time) for _ in range(self.max_retries)]
            )

            patched_time.sleep.assert_has_calls(
                [call(self.xray_service_graph_puller._poll_interval) for _ in range(self.max_retries)]
            )

            patched_load_time_period.assert_has_calls([call(ANY, ANY) for _ in range(self.max_retries)])

    @patch("samcli.lib.observability.xray_traces.xray_event_puller.time")
    @patch("samcli.lib.observability.xray_traces.xray_event_puller.to_timestamp")
    @patch("samcli.lib.observability.xray_traces.xray_event_puller.to_datetime")
    def test_tail_with_with_data(self, patched_to_datetime, patched_to_timestamp, patched_time):
        start_time = Mock()
        given_start_time = 5
        patched_to_timestamp.return_value = 5
        with patch.object(self.xray_service_graph_puller, "_had_data") as patched_had_data:
            patched_had_data.side_effect = [True, False]

            with patch.object(self.xray_service_graph_puller, "load_time_period") as patched_load_time_period:
                self.xray_service_graph_puller.tail(start_time)

                patched_to_timestamp.assert_called_with(start_time)

                patched_to_datetime.assert_has_calls(
                    [
                        call(given_start_time),
                    ],
                    any_order=True,
                )
                patched_to_datetime.assert_has_calls([call(given_start_time + 1) for _ in range(self.max_retries)])

                patched_time.sleep.assert_has_calls(
                    [call(self.xray_service_graph_puller._poll_interval) for _ in range(self.max_retries + 1)]
                )

                patched_load_time_period.assert_has_calls([call(ANY, ANY) for _ in range(self.max_retries + 1)])

    @patch("samcli.lib.observability.xray_traces.xray_event_puller.time")
    def test_with_throttling(self, patched_time):
        with patch.object(
            self.xray_service_graph_puller, "load_time_period", wraps=self.xray_service_graph_puller.load_time_period
        ) as patched_load_time_period:
            patched_load_time_period.side_effect = [
                ClientError({"Error": {"Code": "ThrottlingException"}}, "operation") for _ in range(self.max_retries)
            ]

            self.xray_service_graph_puller.tail()

            patched_load_time_period.assert_has_calls([call(ANY, ANY) for _ in range(self.max_retries)])

            patched_time.sleep.assert_has_calls([call(2), call(4), call(16), call(256)])

            self.assertEqual(self.xray_service_graph_puller._poll_interval, 256)
