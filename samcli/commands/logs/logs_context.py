
import logging
import boto3
import click

from samcli.lib.logs.fetcher import LogsFetcher
from samcli.lib.logs.formatter import LogsFormatter, LambdaLogMsgFormatters, JSONMsgFormatter, KeywordHighlighter
from samcli.lib.logs.provider import LogGroupProvider
from samcli.lib.utils.colors import Colored
from samcli.lib.utils.time import to_utc, parse_date

LOG = logging.getLogger(__name__)


class LogsCommandContext(object):
    """
    Sets up a context to run the Logs command by parsing the CLI arguments and creating necessary objects to be able
    to fetch and display logs

    This class **must** be used inside a ``with`` statement as follows:

        with LogsCommandContext(**kwargs) as context:
            context.fetcher.fetch(...)
    """

    def __init__(self,
                 function_name,
                 stack_name=None,
                 filter_pattern=None,
                 tailing=None,
                 start_time=None,
                 end_time=None,
                 output_file=None):
        """
        Initializes the context

        Parameters
        ----------
        function_name : str
            Name of the function to fetch logs for

        stack_name : str
            Name of the stack where the function is available

        filter_pattern : str
            Optional pattern to filter the logs by

        tailing : bool
            Set to True, if we are tailing logs (ie. wait & fetch new logs as they arrive)

        start_time : str
            Fetch logs starting at this time

        end_time : str
            Fetch logs up to this time

        output_file : str
            Write logs to this file instead of Terminal
        """

        self._function_name = function_name
        self._stack_name = stack_name
        self._filter_pattern = filter_pattern
        self._tailing = tailing
        self._start_time = start_time
        self._end_time = end_time
        self._output_file = output_file

        self._logs_client = boto3.client('logs')

    def __enter__(self):
        """
        Performs some basic checks and returns itself when everything is ready to invoke a Lambda function.

        :returns InvokeContext: Returns this object
        """

        return self

    def __exit__(self, *args):
        """
        Cleanup any necessary opened files
        """
        pass


    @property
    def fetcher(self):
        return LogsFetcher(self._logs_client)

    @property
    def formatter(self):
        formatter_chain = [
            LambdaLogMsgFormatters.colorize_reports,
            LambdaLogMsgFormatters.colorize_errors,
            KeywordHighlighter(self._filter_pattern).highlight_keywords,
            JSONMsgFormatter.format_json
        ]

        return LogsFormatter(self.colored, formatter_chain)

    @property
    def start_time(self):
        if self._start_time:
            parsed = parse_date(self._start_time)
            if not parsed:
                raise click.ClickException("start_time argument is invalid")

            return to_utc(parsed)

    @property
    def end_time(self):
        if self._end_time:
            parsed = parse_date(self._end_time)

            if not parsed:
                raise click.ClickException("end_time argument is invalid")

            return to_utc(parsed)

    @property
    def log_group_name(self):
        return LogGroupProvider.for_lambda_function(self._function_name)

    @property
    def colored(self):
        return Colored(colorize=not self._output_file)

    @property
    def filter_pattern(self):
        return self._filter_pattern
