"""
Read and parse CLI args for the Logs Command and setup the context for running the command
"""

import logging
import boto3
import botocore

from samcli.commands.exceptions import UserException
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
        self._start_time = start_time
        self._end_time = end_time
        self._output_file = output_file
        self._output_file_handle = None

        # No colors when we write to a file. Otherwise use colors
        self._must_print_colors = not self._output_file

        self._logs_client = boto3.client('logs')
        self._cfn_client = boto3.client('cloudformation')

    def __enter__(self):
        """
        Performs some basic checks and returns itself when everything is ready to invoke a Lambda function.

        Returns
        -------
        LogsCommandContext
            Returns this object
        """

        self._output_file_handle = self._setup_output_file(self._output_file)

        return self

    def __exit__(self, *args):
        """
        Cleanup any necessary opened files
        """

        if self._output_file_handle:
            self._output_file_handle.close()
            self._output_file_handle = None

    @property
    def fetcher(self):
        return LogsFetcher(self._logs_client)

    @property
    def formatter(self):
        """
        Creates and returns a Formatter capable of nicely formatting Lambda function logs

        Returns
        -------
        LogsFormatter
        """
        formatter_chain = [
            LambdaLogMsgFormatters.colorize_errors,

            # Format JSON "before" highlighting the keywords. Otherwise, JSON will be invalid from all the
            # ANSI color codes and fail to pretty print
            JSONMsgFormatter.format_json,

            KeywordHighlighter(self._filter_pattern).highlight_keywords,
        ]

        return LogsFormatter(self.colored, formatter_chain)

    @property
    def start_time(self):
        return self._parse_time(self._start_time, 'start-time')

    @property
    def end_time(self):
        return self._parse_time(self._end_time, 'end-time')

    @property
    def log_group_name(self):
        """
        Name of the AWS CloudWatch Log Group that we will be querying. It generates the name based on the
        Lambda Function name and stack name provided.

        Returns
        -------
        str
            Name of the CloudWatch Log Group
        """

        function_id = self._function_name
        if self._stack_name:
            function_id = self._get_resource_id_from_stack(self._cfn_client, self._stack_name, self._function_name)
            LOG.debug("Function with LogicalId '%s' in stack '%s' resolves to actual physical ID '%s'",
                      self._function_name, self._stack_name, function_id)

        return LogGroupProvider.for_lambda_function(function_id)

    @property
    def colored(self):
        """
        Instance of Colored object to colorize strings

        Returns
        -------
        samcli.commands.utils.colors.Colored
        """
        # No colors if we are writing output to a file
        return Colored(colorize=self._must_print_colors)

    @property
    def filter_pattern(self):
        return self._filter_pattern

    @property
    def output_file_handle(self):
        return self._output_file_handle

    @staticmethod
    def _setup_output_file(output_file):
        """
        Open a log file if necessary and return the file handle. This will create a file if it does not exist

        Parameters
        ----------
        output_file : str
            Path to a file where the logs should be written to

        Returns
        -------
        Handle to the opened log file, if necessary. None otherwise
        """
        if not output_file:
            return None

        return open(output_file, 'wb')

    @staticmethod
    def _parse_time(time_str, property_name):
        """
        Parse the time from the given string, convert to UTC, and return the datetime object

        Parameters
        ----------
        time_str : str
            The time to parse

        property_name : str
            Name of the property where this time came from. Used in the exception raised if time is not parseable

        Returns
        -------
        datetime.datetime
            Parsed datetime object

        Raises
        ------
        samcli.commands.exceptions.UserException
            If the string cannot be parsed as a timestamp
        """
        if not time_str:
            return

        parsed = parse_date(time_str)
        if not parsed:
            raise UserException("Unable to parse the time provided by '{}'".format(property_name))

        return to_utc(parsed)

    @staticmethod
    def _get_resource_id_from_stack(cfn_client, stack_name, logical_id):
        """
        Given the LogicalID of a resource, call AWS CloudFormation to get physical ID of the resource within
        the specified stack.

        Parameters
        ----------
        cfn_client
            CloudFormation client provided by AWS SDK

        stack_name : str
            Name of the stack to query

        logical_id : str
            LogicalId of the resource

        Returns
        -------
        str
            Physical ID of the resource

        Raises
        ------
        samcli.commands.exceptions.UserException
            If the stack or resource does not exist
        """

        LOG.debug("Getting resource's PhysicalId from AWS CloudFormation stack. StackName=%s, LogicalId=%s",
                  stack_name, logical_id)

        try:
            response = cfn_client.describe_stack_resource(StackName=stack_name, LogicalResourceId=logical_id)

            LOG.debug("Response from AWS CloudFormation %s", response)
            return response["StackResourceDetail"]["PhysicalResourceId"]

        except botocore.exceptions.ClientError as ex:
            LOG.debug("Unable to fetch resource name from CloudFormation Stack: "
                      "StackName=%s, ResourceLogicalId=%s, Response=%s", stack_name, logical_id, ex.response)

            # The exception message already has a well formatted error message that we can surface to user
            raise UserException(str(ex))
