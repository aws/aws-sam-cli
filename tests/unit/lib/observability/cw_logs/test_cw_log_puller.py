import copy
from datetime import datetime
from unittest import TestCase
from unittest.mock import Mock, call, patch, ANY

import botocore.session
from botocore.stub import Stubber

from samcli.lib.observability.cw_logs.cw_log_event import CWLogEvent
from samcli.lib.observability.cw_logs.cw_log_puller import CWLogPuller
from samcli.lib.utils.time import to_timestamp, to_datetime


class TestCWLogPuller_load_time_period(TestCase):
    def setUp(self):
        self.log_group_name = "name"
        self.stream_name = "stream name"
        self.timestamp = to_timestamp(datetime.utcnow())

        real_client = botocore.session.get_session().create_client("logs", region_name="us-east-1")
        self.client_stubber = Stubber(real_client)
        self.consumer = Mock()
        self.fetcher = CWLogPuller(real_client, self.consumer, self.log_group_name)

        self.mock_api_response = {
            "events": [
                {
                    "eventId": "id1",
                    "ingestionTime": 0,
                    "logStreamName": self.stream_name,
                    "message": "message 1",
                    "timestamp": self.timestamp,
                },
                {
                    "eventId": "id2",
                    "ingestionTime": 0,
                    "logStreamName": self.stream_name,
                    "message": "message 2",
                    "timestamp": self.timestamp,
                },
            ]
        }

        self.expected_events = [
            CWLogEvent(
                self.log_group_name,
                {
                    "eventId": "id1",
                    "ingestionTime": 0,
                    "logStreamName": self.stream_name,
                    "message": "message 1",
                    "timestamp": self.timestamp,
                },
            ),
            CWLogEvent(
                self.log_group_name,
                {
                    "eventId": "id2",
                    "ingestionTime": 0,
                    "logStreamName": self.stream_name,
                    "message": "message 2",
                    "timestamp": self.timestamp,
                },
            ),
        ]

    def test_must_fetch_logs_for_log_group(self):
        expected_params = {"logGroupName": self.log_group_name, "interleaved": True}

        # Configure the stubber to return the configured response. The stubber also verifies
        # that input params were provided as expected
        self.client_stubber.add_response("filter_log_events", self.mock_api_response, expected_params)

        with self.client_stubber:
            self.fetcher.load_time_period()

            call_args = [args[0] for (args, _) in self.consumer.consume.call_args_list]
            for event in self.expected_events:
                self.assertIn(event, call_args)

    def test_must_fetch_logs_with_all_params(self):
        pattern = "foobar"
        start = datetime.utcnow()
        end = datetime.utcnow()

        expected_params = {
            "logGroupName": self.log_group_name,
            "interleaved": True,
            "startTime": to_timestamp(start),
            "endTime": to_timestamp(end),
            "filterPattern": pattern,
        }

        self.client_stubber.add_response("filter_log_events", self.mock_api_response, expected_params)

        with self.client_stubber:
            self.fetcher.load_time_period(start_time=start, end_time=end, filter_pattern=pattern)

            call_args = [args[0] for (args, _) in self.consumer.consume.call_args_list]
            for event in self.expected_events:
                self.assertIn(event, call_args)

    @patch("samcli.lib.observability.cw_logs.cw_log_puller.LOG")
    def test_must_print_resource_not_found_only_once(self, patched_log):
        pattern = "foobar"
        start = datetime.utcnow()
        end = datetime.utcnow()

        expected_params = {
            "logGroupName": self.log_group_name,
            "interleaved": True,
            "startTime": to_timestamp(start),
            "endTime": to_timestamp(end),
            "filterPattern": pattern,
        }

        self.client_stubber.add_client_error(
            "filter_log_events", expected_params=expected_params, service_error_code="ResourceNotFoundException"
        )
        self.client_stubber.add_client_error(
            "filter_log_events", expected_params=expected_params, service_error_code="ResourceNotFoundException"
        )
        self.client_stubber.add_response("filter_log_events", self.mock_api_response, expected_params)

        with self.client_stubber:
            self.assertFalse(self.fetcher._invalid_log_group)
            self.fetcher.load_time_period(start_time=start, end_time=end, filter_pattern=pattern)
            self.assertTrue(self.fetcher._invalid_log_group)
            self.fetcher.load_time_period(start_time=start, end_time=end, filter_pattern=pattern)
            self.assertTrue(self.fetcher._invalid_log_group)
            self.fetcher.load_time_period(start_time=start, end_time=end, filter_pattern=pattern)
            self.assertFalse(self.fetcher._invalid_log_group)

    def test_must_paginate_using_next_token(self):
        """Make three API calls, first two returns a nextToken and last does not."""
        token = "token"
        expected_params = {"logGroupName": self.log_group_name, "interleaved": True}
        expected_params_with_token = {"logGroupName": self.log_group_name, "interleaved": True, "nextToken": token}

        mock_response_with_token = copy.deepcopy(self.mock_api_response)
        mock_response_with_token["nextToken"] = token

        # Call 1 returns a token. Also when first call is made, token is **not** passed as API params
        self.client_stubber.add_response("filter_log_events", mock_response_with_token, expected_params)

        # Call 2 returns a token
        self.client_stubber.add_response("filter_log_events", mock_response_with_token, expected_params_with_token)

        # Call 3 DOES NOT return a token. This will terminate the loop.
        self.client_stubber.add_response("filter_log_events", self.mock_api_response, expected_params_with_token)

        # Same data was returned in each API call
        expected_events_result = self.expected_events + self.expected_events + self.expected_events

        with self.client_stubber:
            self.fetcher.load_time_period()

            call_args = [args[0] for (args, _) in self.consumer.consume.call_args_list]
            for event in expected_events_result:
                self.assertIn(event, call_args)


class TestCWLogPuller_tail(TestCase):
    def setUp(self):
        self.log_group_name = "name"
        self.filter_pattern = "pattern"
        self.start_time = to_datetime(10)
        self.max_retries = 3
        self.poll_interval = 1

        real_client = botocore.session.get_session().create_client("logs", region_name="us-east-1")
        self.client_stubber = Stubber(real_client)
        self.consumer = Mock()
        self.fetcher = CWLogPuller(
            real_client,
            self.consumer,
            self.log_group_name,
            max_retries=self.max_retries,
            poll_interval=self.poll_interval,
        )

        self.mock_api_empty_response = {"events": []}
        self.mock_api_response_1 = {
            "events": [
                {
                    "timestamp": 11,
                },
                {
                    "timestamp": 12,
                },
            ]
        }
        self.mock_api_response_2 = {
            "events": [
                {
                    "timestamp": 13,
                },
                {
                    "timestamp": 14,
                },
            ]
        }

        self.mock_events1 = [
            CWLogEvent(self.log_group_name, {"timestamp": 11}),
            CWLogEvent(self.log_group_name, {"timestamp": 12}),
        ]
        self.mock_events2 = [
            CWLogEvent(self.log_group_name, {"timestamp": 13}),
            CWLogEvent(self.log_group_name, {"timestamp": 14}),
        ]
        self.mock_events_empty = []

    @patch("samcli.lib.observability.cw_logs.cw_log_puller.time")
    def test_must_tail_logs_with_single_data_fetch(self, time_mock):
        expected_params = {
            "logGroupName": self.log_group_name,
            "interleaved": True,
            "startTime": 10,
            "filterPattern": self.filter_pattern,
        }
        expected_params_second_try = {
            "logGroupName": self.log_group_name,
            "interleaved": True,
            "startTime": 13,
            "filterPattern": self.filter_pattern,
        }

        # first successful return
        self.client_stubber.add_response("filter_log_events", self.mock_api_response_1, expected_params)
        # 3 empty returns as the number of max retries
        self.client_stubber.add_response("filter_log_events", self.mock_api_empty_response, expected_params_second_try)
        self.client_stubber.add_response("filter_log_events", self.mock_api_empty_response, expected_params_second_try)
        self.client_stubber.add_response("filter_log_events", self.mock_api_empty_response, expected_params_second_try)

        with patch.object(
            self.fetcher, "load_time_period", wraps=self.fetcher.load_time_period
        ) as patched_load_time_period:
            with self.client_stubber:
                self.fetcher.tail(
                    start_time=self.start_time,
                    filter_pattern=self.filter_pattern,
                )

                expected_load_time_period_calls = [
                    # First fetch returns data
                    call(self.start_time, filter_pattern=self.filter_pattern),
                    # Three empty fetches
                    call(to_datetime(13), filter_pattern=self.filter_pattern),
                    call(to_datetime(13), filter_pattern=self.filter_pattern),
                    call(to_datetime(13), filter_pattern=self.filter_pattern),
                ]

                # One per poll
                expected_sleep_calls = [call(self.poll_interval) for _ in expected_load_time_period_calls]

                consumer_call_args = [args[0] for (args, _) in self.consumer.consume.call_args_list]

                self.assertEqual(self.mock_events1, consumer_call_args)
                self.assertEqual(expected_sleep_calls, time_mock.sleep.call_args_list)
                self.assertEqual(expected_load_time_period_calls, patched_load_time_period.call_args_list)

    @patch("samcli.lib.observability.cw_logs.cw_log_puller.time")
    def test_must_tail_logs_with_multiple_data_fetches(self, time_mock):
        expected_params = {
            "logGroupName": self.log_group_name,
            "interleaved": True,
            "startTime": 10,
            "filterPattern": self.filter_pattern,
        }
        expected_params_second_try = {
            "logGroupName": self.log_group_name,
            "interleaved": True,
            "startTime": 13,
            "filterPattern": self.filter_pattern,
        }
        expected_params_third_try = {
            "logGroupName": self.log_group_name,
            "interleaved": True,
            "startTime": 15,
            "filterPattern": self.filter_pattern,
        }

        self.client_stubber.add_response("filter_log_events", self.mock_api_response_1, expected_params)
        self.client_stubber.add_response("filter_log_events", self.mock_api_empty_response, expected_params_second_try)
        self.client_stubber.add_response("filter_log_events", self.mock_api_response_2, expected_params_second_try)
        self.client_stubber.add_response("filter_log_events", self.mock_api_empty_response, expected_params_third_try)
        self.client_stubber.add_response("filter_log_events", self.mock_api_empty_response, expected_params_third_try)
        self.client_stubber.add_response("filter_log_events", self.mock_api_empty_response, expected_params_third_try)

        expected_load_time_period_calls = [
            # First fetch returns data
            call(self.start_time, filter_pattern=self.filter_pattern),
            # This fetch was empty
            call(to_datetime(13), filter_pattern=self.filter_pattern),
            # This fetch returned data
            call(to_datetime(13), filter_pattern=self.filter_pattern),
            # Three empty fetches
            call(to_datetime(15), filter_pattern=self.filter_pattern),
            call(to_datetime(15), filter_pattern=self.filter_pattern),
            call(to_datetime(15), filter_pattern=self.filter_pattern),
        ]

        # One per poll
        expected_sleep_calls = [call(self.poll_interval) for _ in expected_load_time_period_calls]

        with patch.object(
            self.fetcher, "load_time_period", wraps=self.fetcher.load_time_period
        ) as patched_load_time_period:
            with self.client_stubber:
                self.fetcher.tail(start_time=self.start_time, filter_pattern=self.filter_pattern)

                expected_consumer_call_args = [args[0] for (args, _) in self.consumer.consume.call_args_list]

                self.assertEqual(self.mock_events1 + self.mock_events2, expected_consumer_call_args)
                self.assertEqual(expected_load_time_period_calls, patched_load_time_period.call_args_list)
                self.assertEqual(expected_sleep_calls, time_mock.sleep.call_args_list)

    @patch("samcli.lib.observability.cw_logs.cw_log_puller.time")
    def test_without_start_time(self, time_mock):
        expected_params = {
            "logGroupName": self.log_group_name,
            "interleaved": True,
            "startTime": 0,
            "filterPattern": self.filter_pattern,
        }
        self.client_stubber.add_response("filter_log_events", self.mock_api_empty_response, expected_params)
        self.client_stubber.add_response("filter_log_events", self.mock_api_empty_response, expected_params)
        self.client_stubber.add_response("filter_log_events", self.mock_api_empty_response, expected_params)

        expected_load_time_period_calls = [
            # Three empty fetches, all with default start time
            call(to_datetime(0), filter_pattern=ANY),
            call(to_datetime(0), filter_pattern=ANY),
            call(to_datetime(0), filter_pattern=ANY),
        ]

        # One per poll
        expected_sleep_calls = [call(self.poll_interval) for _ in expected_load_time_period_calls]

        with patch.object(
            self.fetcher, "load_time_period", wraps=self.fetcher.load_time_period
        ) as patched_load_time_period:
            with self.client_stubber:
                self.fetcher.tail(
                    filter_pattern=self.filter_pattern,
                )

                expected_consumer_call_args = [args[0] for (args, _) in self.consumer.consume.call_args_list]

                self.assertEqual([], expected_consumer_call_args)
                self.assertEqual(expected_load_time_period_calls, patched_load_time_period.call_args_list)
                self.assertEqual(expected_sleep_calls, time_mock.sleep.call_args_list)

    @patch("samcli.lib.observability.cw_logs.cw_log_puller.time")
    def test_with_throttling(self, time_mock):
        expected_params = {
            "logGroupName": self.log_group_name,
            "interleaved": True,
            "startTime": 0,
            "filterPattern": self.filter_pattern,
        }

        for _ in range(self.max_retries):
            self.client_stubber.add_client_error(
                "filter_log_events", expected_params=expected_params, service_error_code="ThrottlingException"
            )

        expected_load_time_period_calls = [call(to_datetime(0), filter_pattern=ANY) for _ in range(self.max_retries)]

        expected_time_calls = [call(2), call(4), call(16)]

        with patch.object(
            self.fetcher, "load_time_period", wraps=self.fetcher.load_time_period
        ) as patched_load_time_period:
            with self.client_stubber:
                self.fetcher.tail(filter_pattern=self.filter_pattern)

                self.consumer.consume.assert_not_called()
                self.assertEqual(expected_load_time_period_calls, patched_load_time_period.call_args_list)
                time_mock.sleep.assert_has_calls(expected_time_calls, any_order=True)
