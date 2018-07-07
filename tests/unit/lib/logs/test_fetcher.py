
import copy
import datetime
import botocore.session

from unittest import TestCase
from botocore.stub import Stubber

from samcli.lib.logs.fetcher import LogsFetcher
from samcli.lib.logs.event import LogEvent
from samcli.lib.utils.time import to_timestamp


class TestLogsFetcher_fetch(TestCase):

    def setUp(self):

        real_client = botocore.session.get_session().create_client('logs', region_name="us-east-1")
        self.client_stubber = Stubber(real_client)
        self.fetcher = LogsFetcher(real_client)

        self.log_group_name = "name"
        self.stream_name = "stream name"
        self.timestamp = to_timestamp(datetime.datetime.utcnow())

        self.mock_api_response = {
            "events": [
                {
                    "eventId": "id1",
                    "ingestionTime": 0,
                    "logStreamName": self.stream_name,
                    "message": "message 1",
                    "timestamp": self.timestamp
                },

                {
                    "eventId": "id2",
                    "ingestionTime": 0,
                    "logStreamName": self.stream_name,
                    "message": "message 2",
                    "timestamp": self.timestamp
                }
            ]
        }

        self.expected_events = [
                LogEvent(self.log_group_name, {
                    "eventId": "id1",
                    "ingestionTime": 0,
                    "logStreamName": self.stream_name,
                    "message": "message 1",
                    "timestamp": self.timestamp
                }),

                LogEvent(self.log_group_name, {
                    "eventId": "id2",
                    "ingestionTime": 0,
                    "logStreamName": self.stream_name,
                    "message": "message 2",
                    "timestamp": self.timestamp
                })
        ]

    def test_must_fetch_logs_for_log_group(self):
        expected_params = {
            "logGroupName": self.log_group_name,
            "interleaved": True
        }

        # Configure the stubber to return the configured response. The stubber also verifies
        # that input params were provided as expected
        self.client_stubber.add_response('filter_log_events', self.mock_api_response, expected_params)

        with self.client_stubber:
            events_iterable = self.fetcher.fetch(self.log_group_name)

            actual_result = list(events_iterable)
            self.assertEquals(self.expected_events, actual_result)

    def test_must_fetch_logs_with_all_params(self):
        pattern = "foobar"
        start = datetime.datetime.utcnow()
        end = datetime.datetime.utcnow()

        expected_params = {
            "logGroupName": self.log_group_name,
            "interleaved": True,
            "startTime": to_timestamp(start),
            "endTime": to_timestamp(end),
            "filterPattern": pattern
        }

        self.client_stubber.add_response('filter_log_events', self.mock_api_response, expected_params)

        with self.client_stubber:
            events_iterable = self.fetcher.fetch(self.log_group_name, start=start, end=end, filter_pattern=pattern)

            actual_result = list(events_iterable)
            self.assertEquals(self.expected_events, actual_result)

    def test_must_paginate_using_next_token(self):
        """Make three API calls, first two returns a nextToken and last does not."""
        token = "token"
        expected_params = {
            "logGroupName": self.log_group_name,
            "interleaved": True
        }
        expected_params_with_token = {
            "logGroupName": self.log_group_name,
            "interleaved": True,
            "nextToken": token
        }

        mock_response_with_token = copy.deepcopy(self.mock_api_response)
        mock_response_with_token["nextToken"] = token

        # Call 1 returns a token. Also when first call is made, token is **not** passed as API params
        self.client_stubber.add_response('filter_log_events', mock_response_with_token, expected_params)

        # Call 2 returns a token
        self.client_stubber.add_response('filter_log_events', mock_response_with_token, expected_params_with_token)

        # Call 3 DOES NOT return a token. This will terminate the loop.
        self.client_stubber.add_response('filter_log_events', self.mock_api_response, expected_params_with_token)

        # Same data was returned in each API call
        expected_events_result = self.expected_events + self.expected_events + self.expected_events

        with self.client_stubber:
            events_iterable = self.fetcher.fetch(self.log_group_name)

            actual_result = list(events_iterable)
            self.assertEquals(expected_events_result, actual_result)
