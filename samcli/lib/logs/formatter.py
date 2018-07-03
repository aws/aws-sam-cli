

class LogsFormatter(object):
    """
    Formatter of
    """

    def format(self, event_iterable):
        """
        Formats the given CloudWatch Logs Event dictionary as necessary and yields a formatted string. This can be
        used to parse and format the events based on context ie. In Lambda Function logs, a formatter may wish to
        color the "ERROR" keywords red, or highlight a filter keyword separately etc.

        Parameters
        ----------
        event_iterable : iterable
            Iterable that returns a dictionary of log events as output by CloudWatch Logs API.
            Check out the docs for reference:
                https://docs.aws.amazon.com/AmazonCloudWatchLogs/latest/APIReference/API_FilteredLogEvent.html

        log_group_name : string
            Name of the log group that this event was generated from

        Yields
        -------
        string
            Formatted string
        """
        raise NotImplementedError("Must subclass the formatter")

operations = [formatter.format, ]
itr = logs.fetch()
for op in operations:
    op(itr)
