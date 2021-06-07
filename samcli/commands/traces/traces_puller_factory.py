"""
Factory methods which generates puller and consumer instances for XRay events
"""
from typing import Any, Optional

from samcli.commands.traces.trace_console_consumers import XRayTraceConsoleConsumer
from samcli.lib.observability.observability_info_puller import (
    ObservabilityPuller,
    ObservabilityEventConsumer,
    ObservabilityEventConsumerDecorator,
)
from samcli.lib.observability.xray_traces.xray_event_consumers import XRayEventFileConsumer
from samcli.lib.observability.xray_traces.xray_event_mappers import XRayTraceConsoleMapper, XRayTraceFileMapper
from samcli.lib.observability.xray_traces.xray_event_puller import XRayTracePuller


def generate_trace_puller(
    xray_client: Any,
    output_dir: Optional[str],
) -> ObservabilityPuller:
    """
    Generates puller instance with correct consumer and/or mapper configuration

    Parameters
    ----------
    xray_client : Any
        boto3 xray client to be used in XRayTracePuller instance
    output_dir : Optional[str]
        Optional output directory configuration. If given it will generate puller with
        file consumer, otherwise it will generate puller with console consumer.

    Returns
    -------
        Puller instance with desired configuration
    """
    if output_dir:
        consumer = generate_file_consumer(output_dir)
    else:
        consumer = generate_console_consumer()

    return XRayTracePuller(xray_client, consumer)


def generate_file_consumer(output_dir: str) -> ObservabilityEventConsumer:
    """
    Generates file consumer, which will store XRay events into a file in given folder

    Parameters
    ----------
    output_dir : str
        Location of the output directory where events and file will be stored.

    Returns
    -------
        File consumer instance with desired mapper configuration
    """
    return ObservabilityEventConsumerDecorator([XRayTraceFileMapper()], XRayEventFileConsumer(output_dir))


def generate_console_consumer() -> ObservabilityEventConsumer:
    """
    Generates an instance of event consumer which will print events into console

    Returns
    -------
        Console consumer instance with desired mapper configuration
    """
    return ObservabilityEventConsumerDecorator([XRayTraceConsoleMapper()], XRayTraceConsoleConsumer())
