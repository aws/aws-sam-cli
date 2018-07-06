"""
CLI command for "logs" command
"""

import logging
import click

from samcli.cli.main import pass_context, common_options as cli_framework_options
from .logs_context import LogsCommandContext

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


def do_cli(ctx, function_name, stack_name, filter_pattern, tailing, start_time, end_time):
    """
    Implementation of the ``cli`` method, just separated out for unit testing purposes
    """

    LOG.debug("'logs' command is called")

    with LogsCommandContext(function_name,
                            stack_name=stack_name,
                            filter_pattern=filter_pattern,
                            tailing=tailing,
                            start_time=start_time,
                            end_time=end_time,
                            output_file=None) as context:

        events_iterable = context.fetcher.fetch(context.log_group_name,
                                                filter_pattern=context.filter_pattern,
                                                start=context.start_time,
                                                end=context.end_time)

        formatted_events = context.formatter.do_format(events_iterable)

        for event in formatted_events:
            click.echo(event, nl=False)
