"""
File keeps Factory method to prepare required puller information
with its producers and consumers
"""
import logging
from typing import List, Optional

from samcli.commands.exceptions import UserException
from samcli.commands.logs.console_consumers import CWConsoleEventConsumer
from samcli.commands.traces.traces_puller_factory import generate_trace_puller
from samcli.lib.observability.cw_logs.cw_log_formatters import (
    CWColorizeErrorsFormatter,
    CWJsonFormatter,
    CWKeywordHighlighterFormatter,
    CWPrettyPrintFormatter,
    CWAddNewLineIfItDoesntExist,
    CWLogEventJSONMapper,
)
from samcli.lib.observability.cw_logs.cw_log_group_provider import LogGroupProvider
from samcli.lib.observability.cw_logs.cw_log_puller import CWLogPuller
from samcli.lib.observability.observability_info_puller import (
    ObservabilityPuller,
    ObservabilityEventConsumerDecorator,
    ObservabilityEventConsumer,
    ObservabilityCombinedPuller,
)
from samcli.lib.utils.boto_utils import BotoProviderType
from samcli.lib.utils.cloudformation import CloudFormationResourceSummary
from samcli.lib.utils.colors import Colored

LOG = logging.getLogger(__name__)


class NoPullerGeneratedException(UserException):
    """
    Used to indicate that no puller information have been generated
    therefore there is no observability information (logs, xray) to pull
    """


def generate_puller(
    boto_client_provider: BotoProviderType,
    resource_information_list: List[CloudFormationResourceSummary],
    filter_pattern: Optional[str] = None,
    additional_cw_log_groups: Optional[List[str]] = None,
    unformatted: bool = False,
    include_tracing: bool = False,
) -> ObservabilityPuller:
    """
    This function will generate generic puller which can be used to
    pull information from various observability resources.

    Parameters
    ----------
    boto_client_provider: BotoProviderType
        Boto3 client generator, which will create a new instance of the client with a new session that could be
        used within different threads/coroutines
    resource_information_list : List[CloudFormationResourceSummary]
        List of resource information, which keeps logical id, physical id and type of the resources
    filter_pattern : Optional[str]
        Optional filter pattern which will be used to filter incoming events
    additional_cw_log_groups : Optional[str]
        Optional list of additional CloudWatch log groups which will be used to fetch
        log events from.
    unformatted : bool
        By default, logs and traces are printed with a format for terminal. If this option is provided, the events
        will be printed unformatted in JSON.
    include_tracing: bool
        A flag to include the xray traces log or not

    Returns
    -------
        Puller instance that can be used to pull information.
    """
    if additional_cw_log_groups is None:
        additional_cw_log_groups = []
    pullers: List[ObservabilityPuller] = []

    # populate all puller instances for given resources
    for resource_information in resource_information_list:
        cw_log_group_name = LogGroupProvider.for_resource(
            boto_client_provider,
            resource_information.resource_type,
            resource_information.physical_resource_id,
        )
        if not cw_log_group_name:
            LOG.debug("Can't find CloudWatch LogGroup name for resource (%s)", resource_information.logical_resource_id)
            continue

        consumer = generate_consumer(filter_pattern, unformatted, resource_information.logical_resource_id)
        pullers.append(
            CWLogPuller(
                boto_client_provider("logs"),
                consumer,
                cw_log_group_name,
                resource_information.logical_resource_id,
            )
        )

    # populate puller instances for the additional CloudWatch log groups
    for cw_log_group in additional_cw_log_groups:
        consumer = generate_consumer(filter_pattern, unformatted)
        pullers.append(
            CWLogPuller(
                boto_client_provider("logs"),
                consumer,
                cw_log_group,
            )
        )

    # if tracing flag is set, add the xray traces puller to fetch debug traces
    if include_tracing:
        trace_puller = generate_trace_puller(boto_client_provider("xray"), unformatted)
        pullers.append(trace_puller)

    # if no puller have been collected, raise an exception since there is nothing to pull
    if not pullers:
        raise NoPullerGeneratedException("No valid resources find to pull information")

    # return the combined puller instance, which will pull from all pullers collected
    return ObservabilityCombinedPuller(pullers)


def generate_consumer(
    filter_pattern: Optional[str] = None, unformatted: bool = False, resource_name: Optional[str] = None
):
    """
    Generates consumer instance with the given variables.
    If unformatted is True, then it will return consumer with formatters for just JSON.
    If not, it will return console consumer
    """
    if unformatted:
        return generate_unformatted_consumer()

    return generate_console_consumer(filter_pattern)


def generate_unformatted_consumer() -> ObservabilityEventConsumer:
    """
    Creates event consumer, which prints CW Log Events unformatted as JSON into terminal

    Returns
    -------
        ObservabilityEventConsumer which will store events into a file
    """
    return ObservabilityEventConsumerDecorator(
        [
            CWLogEventJSONMapper(),
        ],
        CWConsoleEventConsumer(True),
    )


def generate_console_consumer(filter_pattern: Optional[str]) -> ObservabilityEventConsumer:
    """
    Creates a console event consumer, which is used to display events in the user's console

    Parameters
    ----------
    filter_pattern : str
        Filter pattern is used to display certain words in a different pattern then
        the rest of the messages.

    Returns
    -------
        A consumer which will display events into console
    """
    colored = Colored()
    return ObservabilityEventConsumerDecorator(
        [
            CWColorizeErrorsFormatter(colored),
            CWJsonFormatter(),
            CWKeywordHighlighterFormatter(colored, filter_pattern),
            CWPrettyPrintFormatter(colored),
            CWAddNewLineIfItDoesntExist(),
        ],
        CWConsoleEventConsumer(),
    )
