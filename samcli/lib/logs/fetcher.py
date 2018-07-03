"""

"""


class LogsFetcher(object):
    """
    Fetch logs from a CloudWatch Logs group with the ability to scope to a particular time, filter by
    a pattern, and in the future possibly multiplex from from multiple streams together.
    """

    def fetch(self, log_group_name, start=None, end=None, filter_pattern=None, formatter=None):
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

        formatter :

        Yields
        ------

        """
        pass

