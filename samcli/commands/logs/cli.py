"""
CLI command for "logs" command
"""

import logging
import click
import dateparser
import datetime
import boto3

from dateutil.tz import tzutc

from samcli.cli.main import pass_context, common_options as cli_framework_options
from samcli.lib.logs.fetcher import LogsFetcher
from samcli.lib.logs.formatter import LogsFormatter, LambdaLogMsgFormatters, JSONMsgFormatter, KeywordHighlighter
from samcli.lib.logs.provider import LogGroupProvider
from samcli.lib.utils.colors import Colored

LOG = logging.getLogger(__name__)

HELP_TEXT = """
Use this command to fetch logs printed by your Lambda function. 
"""


@click.command("logs", help=HELP_TEXT, short_help="Fetch logs for a function")
@click.option("--function", "-f",
              required=True,
              help="Name of the AWS Lambda function. If this function is a part of SAM stack, this can"
                   "be the LogicalID of function resource in SAM template")
@click.option("--stack-name",
              default=None,
              help="Name of AWS CloudFormation stack that the function is a part of")
@click.option("--filter",
              default=None,
              help="Filter logs using this expression. It could be a simple keyword or a complex pattern that is"
                   "supported by AWS CloudWatch Logs. See AWS CloudWatch Logs documentation for pattern syntax - "
                   "https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/FilterAndPatternSyntax.html")
@click.option("--tail", "-t",
              is_flag=True,
              help="Tail the log output. This will ignore the end time argument and continue to fetch logs as they"
                   "become available")
@click.option("--start-time", "-s",
              default='10m ago',
              help="Fetch logs starting at this time. Time can be relative values like '5 mins ago', 'tomorrow' or "
                   "formatted timestamp like '2017-01-01 10:10:10'")
@click.option("--end-time", "-e",
              default=None,
              help="Fetch logs up to this time. Time can be relative values like '5 mins ago', 'tomorrow' or "
                   "formatted timestamp like '2017-01-01 10:10:10'")
@cli_framework_options
@pass_context
def cli(ctx,
        function, stack_name, filter, tail, start_time, end_time
        ):
    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing

    do_cli(ctx, function, stack_name, filter, tail, start_time, end_time)


def do_cli(ctx, function_name, stack_name, filter_pattern, is_watching, start_time, end_time):
    """
    Implementation of the ``cli`` method, just separated out for unit testing purposes
    """

    LOG.debug("'logs' command is called")

    group_name = LogGroupProvider.for_lambda_function(function_name)
    fetcher = LogsFetcher(boto3.client('logs'))

    colored = Colored()
    formatter_chain = [
        LambdaLogMsgFormatters.colorize_reports,
        LambdaLogMsgFormatters.colorize_errors,
        KeywordHighlighter(filter_pattern).highlight_keywords,
        JSONMsgFormatter.format_json
    ]
    formatter = LogsFormatter(colored, formatter_chain)

    parser_settings = {
        # Relative times like '10m ago' must subtract from the current UTC time. Without this setting, dateparser
        # will use current local time as the base for subtraction, but falsely assume it is a UTC time. Therefore
        # the time that dateparser returns will be a `datetime` object that did not have any timezone information.
        # So be explicit to set the time to UTC.
        "RELATIVE_BASE": datetime.datetime.utcnow()
    }

    if start_time:
        start_time = to_utc(dateparser.parse(start_time, settings=parser_settings))

    if end_time:
        end_time = to_utc(dateparser.parse(end_time, settings=parser_settings))

    events_iterable = fetcher.fetch(group_name,
                                    filter_pattern=filter_pattern,
                                    start=start_time,
                                    end=end_time)

    for event in formatter.do_format(events_iterable):
        click.echo(event)


def to_utc(date):
    if date.tzinfo:
        if date.utcoffset != 0:
            date = date.astimezone(tzutc())
        date = date.replace(tzinfo=None)

    return date
