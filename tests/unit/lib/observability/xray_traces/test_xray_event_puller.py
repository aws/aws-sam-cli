import time
import uuid
from itertools import zip_longest
from unittest import TestCase
from unittest.mock import patch, call, Mock, ANY

from botocore.exceptions import ClientError
from parameterized import parameterized

from samcli.lib.observability.xray_traces.xray_event_puller import XRayTracePuller


class TestXrayTracePuller(TestCase):
    def setUp(self):
        self.xray_client = Mock()
        self.consumer = Mock()

        self.max_retries = 4
        self.xray_trace_puller = XRayTracePuller(self.xray_client, self.consumer, self.max_retries)

    @parameterized.expand([(i,) for i in range(1, 15)])
    @patch("samcli.lib.observability.xray_traces.xray_event_puller.XRayTraceEvent")
    def test_load_events(self, size, patched_xray_trace_event):
        ids = [str(uuid.uuid4()) for _ in range(size)]
        batch_ids = list(zip_longest(*([iter(ids)] * 5)))
        trace_dict = {}
        for id in ids:
            trace_dict[id] = 1

        given_paginators = [Mock() for _ in batch_ids]
        self.xray_client.get_paginator.side_effect = given_paginators

        given_results = []
        for i in range(len(batch_ids)):
            given_result = [{"Traces": [Mock() for _ in batch]} for batch in batch_ids]
            given_paginators[i].paginate.return_value = given_result
            given_results.append(given_result)

        collected_events = []

        def dynamic_mock(trace, revision):
            mocked_trace_event = Mock(trace=trace, revision=revision)
            mocked_trace_event.get_latest_event_time.return_value = time.time()
            collected_events.append(mocked_trace_event)
            return mocked_trace_event

        patched_xray_trace_event.side_effect = dynamic_mock

        self.xray_trace_puller.load_events(trace_dict)

        for i in range(len(batch_ids)):
            self.xray_client.get_paginator.assert_called_with("batch_get_traces")
            given_paginators[i].assert_has_calls([call.paginate(TraceIds=list(filter(None, batch_ids[i])))])
            self.consumer.assert_has_calls([call.consume(event) for event in collected_events])
            for event in collected_events:
                event.get_latest_event_time.assert_called_once()

    @parameterized.expand([(i,) for i in range(1, 15)])
    @patch("samcli.lib.observability.xray_traces.xray_event_puller.XRayTraceEvent")
    def test_load_events_with_trace_id(self, size, patched_xray_trace_event):
        ids = [str(uuid.uuid4()) for _ in range(size)]
        batch_ids = list(zip_longest(*([iter(ids)] * 5)))

        given_paginators = [Mock() for _ in batch_ids]
        self.xray_client.get_paginator.side_effect = given_paginators

        given_results = []
        for i in range(len(batch_ids)):
            given_result = [{"Traces": [Mock() for _ in batch]} for batch in batch_ids]
            given_paginators[i].paginate.return_value = given_result
            given_results.append(given_result)

        collected_events = []

        def dynamic_mock(trace):
            mocked_trace_event = Mock(trace=trace)
            mocked_trace_event.get_latest_event_time.return_value = time.time()
            collected_events.append(mocked_trace_event)
            return mocked_trace_event

        patched_xray_trace_event.side_effect = dynamic_mock

        self.xray_trace_puller.load_events(ids)

        for i in range(len(batch_ids)):
            self.xray_client.get_paginator.assert_called_with("batch_get_traces")
            given_paginators[i].assert_has_calls([call.paginate(TraceIds=list(filter(None, batch_ids[i])))])
            self.consumer.assert_has_calls([call.consume(event) for event in collected_events])
            for event in collected_events:
                event.get_latest_event_time.assert_called_once()

    def test_load_events_with_no_event_ids(self):
        self.xray_trace_puller.load_events({})
        self.consumer.assert_not_called()

    def test_load_events_with_no_event_returned(self):
        event_ids = {str(uuid.uuid4()): 1}

        given_paginator = Mock()
        given_paginator.paginate.return_value = [{"Traces": []}]
        self.xray_client.get_paginator.return_value = given_paginator

        self.xray_trace_puller.load_events(event_ids)
        given_paginator.paginate.assert_called_with(TraceIds=list(event_ids.keys()))
        self.consumer.assert_not_called()

    def test_load_time_period(self):
        given_paginator = Mock()
        self.xray_client.get_paginator.return_value = given_paginator

        given_trace_summaries = [{"TraceSummaries": [{"Id": str(uuid.uuid4())} for _ in range(10)]}]
        given_paginator.paginate.return_value = given_trace_summaries

        start_time = "start_time"
        end_time = "end_time"
        with patch.object(self.xray_trace_puller, "load_events") as patched_load_events:
            self.xray_trace_puller.load_time_period(start_time, end_time)
            given_paginator.paginate.assert_called_with(TimeRangeType="TraceId", StartTime=start_time, EndTime=end_time)

            collected_trace_ids = [item.get("Id") for item in given_trace_summaries[0].get("TraceSummaries", [])]
            trace_id_dict = {}
            for trace_id in collected_trace_ids:
                trace_id_dict[trace_id] = ANY
            patched_load_events.assert_called_with(trace_id_dict)

    def test_load_time_period_with_partial_result(self):
        given_paginator = Mock()
        self.xray_client.get_paginator.return_value = given_paginator

        given_trace_summaries = [{"TraceSummaries": [{"Id": str(uuid.uuid4()), "IsPartial": True} for _ in range(10)]}]
        given_paginator.paginate.return_value = given_trace_summaries

        start_time = "start_time"
        end_time = "end_time"
        with patch.object(self.xray_trace_puller, "load_events") as patched_load_events:
            self.xray_trace_puller.load_time_period(start_time, end_time)
            given_paginator.paginate.assert_called_with(TimeRangeType="TraceId", StartTime=start_time, EndTime=end_time)

            patched_load_events.assert_called_with({})

    def test_load_time_period_with_new_revision(self):
        given_paginator = Mock()
        self.xray_client.get_paginator.return_value = given_paginator

        trace_id = str(uuid.uuid4())
        given_trace_summaries = [{"TraceSummaries": [{"Id": trace_id, "Revision": i} for i in range(3)]}]
        given_paginator.paginate.return_value = given_trace_summaries

        start_time = "start_time"
        end_time = "end_time"
        with patch.object(self.xray_trace_puller, "load_events") as patched_load_events:
            self.xray_trace_puller.load_time_period(start_time, end_time)
            given_paginator.paginate.assert_called_with(TimeRangeType="TraceId", StartTime=start_time, EndTime=end_time)

            patched_load_events.assert_called_with({trace_id: 2})

    @patch("samcli.lib.observability.xray_traces.xray_event_puller.time")
    @patch("samcli.lib.observability.xray_traces.xray_event_puller.to_timestamp")
    @patch("samcli.lib.observability.xray_traces.xray_event_puller.to_datetime")
    def test_tail_with_no_data(self, patched_to_datetime, patched_to_timestamp, patched_time):
        start_time = Mock()

        with patch.object(self.xray_trace_puller, "load_time_period") as patched_load_time_period:
            self.xray_trace_puller.tail(start_time)

            patched_to_timestamp.assert_called_with(start_time)

            patched_to_datetime.assert_has_calls(
                [call(self.xray_trace_puller.latest_event_time) for _ in range(self.max_retries)]
            )

            patched_time.sleep.assert_has_calls(
                [call(self.xray_trace_puller._poll_interval) for _ in range(self.max_retries)]
            )

            patched_load_time_period.assert_has_calls([call(ANY, ANY) for _ in range(self.max_retries)])

    @patch("samcli.lib.observability.xray_traces.xray_event_puller.time")
    @patch("samcli.lib.observability.xray_traces.xray_event_puller.to_timestamp")
    @patch("samcli.lib.observability.xray_traces.xray_event_puller.to_datetime")
    def test_tail_with_with_data(self, patched_to_datetime, patched_to_timestamp, patched_time):
        start_time = Mock()
        given_start_time = 5
        patched_to_timestamp.return_value = 5
        with patch.object(self.xray_trace_puller, "_had_data") as patched_had_data:
            patched_had_data.side_effect = [True, False]

            with patch.object(self.xray_trace_puller, "load_time_period") as patched_load_time_period:
                self.xray_trace_puller.tail(start_time)

                patched_to_timestamp.assert_called_with(start_time)

                patched_to_datetime.assert_has_calls(
                    [
                        call(given_start_time),
                    ],
                    any_order=True,
                )
                patched_to_datetime.assert_has_calls([call(given_start_time + 1) for _ in range(self.max_retries)])

                patched_time.sleep.assert_has_calls(
                    [call(self.xray_trace_puller._poll_interval) for _ in range(self.max_retries + 1)]
                )

                patched_load_time_period.assert_has_calls([call(ANY, ANY) for _ in range(self.max_retries + 1)])

    @patch("samcli.lib.observability.xray_traces.xray_event_puller.time")
    def test_with_throttling(self, patched_time):
        with patch.object(
            self.xray_trace_puller, "load_time_period", wraps=self.xray_trace_puller.load_time_period
        ) as patched_load_time_period:
            patched_load_time_period.side_effect = [
                ClientError({"Error": {"Code": "ThrottlingException"}}, "operation") for _ in range(self.max_retries)
            ]

            self.xray_trace_puller.tail()

            patched_load_time_period.assert_has_calls([call(ANY, ANY) for _ in range(self.max_retries)])

            patched_time.sleep.assert_has_calls([call(2), call(4), call(16), call(256)])

            self.assertEqual(self.xray_trace_puller._poll_interval, 256)
