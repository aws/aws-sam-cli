"""
Filters & fetches logs from CloudWatch Logs
"""

import datetime
import boto3

from .event import LogEvent


class LogsFetcher(object):
    """
    Fetch logs from a CloudWatch Logs group with the ability to scope to a particular time, filter by
    a pattern, and in the future possibly multiplex from from multiple streams together.
    """

    def __init__(self, cw_client=None):

        self.cw_client = cw_client or boto3.client('logs')

    def fetch(self, log_group_name, start=None, end=None, filter_pattern=None):
        """
        Fetch logs from all streams under the given CloudWatch Log Group and yields in the output. Optionally, caller
        can filter the logs using a pattern or a start/end time.

        Parameters
        ----------
        log_group_name : string
            Name of CloudWatch Logs Group to query.

        start : datetime.datetime
            Optional start time for logs.

        end : datetime.datetime
            Optional end time for logs.

        filter_pattern : str
            Expression to filter the logs by. This is passed directly to CloudWatch, so any expression supported by
            CloudWatch Logs API is supported here.

        Yields
        ------

        samcli.lib.logs.event.LogEvent
            Object containing the information from each log event returned by CloudWatch Logs
        """

        kwargs = {
            "logGroupName": log_group_name,
            "interleaved": True
        }

        if start:
            kwargs["startTime"] = self.epoch(start)

        if end:
            kwargs["endTime"] = self.epoch(end)

        if filter_pattern:
            kwargs["filterPattern"] = filter_pattern

        while True:
            result = self.cw_client.filter_log_events(**kwargs)

            # Several events will be returned. Yield one at a time
            for event in result.get('events', []):
                yield LogEvent(log_group_name, event)

            # Keep iterating until there are no more logs left to query.
            next_token = result.get("nextToken", None)
            kwargs["nextToken"] = next_token
            if not next_token:
                break

    @staticmethod
    def epoch(some_time):
        """
        Converts the given datetime value to Unix timestamp

        Parameters
        ----------
        some_time : datetime.datetime
            Value to be converted to unix epoch

        Returns
        -------
        int
            Unix timestamp of the given time
        """

        # `total_seconds()` returns elaped microseconds as a float. Get just milliseconds and discard the rest.
        return int((some_time - datetime.datetime(1970, 1, 1)).total_seconds() * 1000.0)
