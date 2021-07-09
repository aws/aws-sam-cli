"""
Factory methods which generates puller and consumer instances for XRay events
"""
from typing import Any, Optional, List

from samcli.commands.traces.trace_console_consumers import XRayTraceConsoleConsumer
from samcli.lib.observability.observability_info_puller import (
    ObservabilityPuller,
    ObservabilityEventConsumer,
    ObservabilityEventConsumerDecorator,
    ObservabilityCombinedPuller,
)
from samcli.lib.observability.xray_traces.xray_event_consumers import XRayEventFileConsumer
from samcli.lib.observability.xray_traces.xray_event_mappers import (
    XRayTraceConsoleMapper,
    XRayTraceFileMapper,
    XRayServiceGraphConsoleMapper,
    XRayServiceGraphFileMapper,
)
from samcli.lib.observability.xray_traces.xray_event_puller import XRayTracePuller
from samcli.lib.observability.xray_traces.xray_service_graph_event_puller import XRayServiceGraphPuller


def generate_trace_puller(
    xray_client: Any,
    output_dir: Optional[str] = None,
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
    pullers: List[ObservabilityPuller] = []
    pullers.append(XRayTracePuller(xray_client, generate_xray_event_consumer(output_dir)))
    pullers.append(XRayServiceGraphPuller(xray_client, generate_xray_service_graph_consumer(output_dir)))

    return ObservabilityCombinedPuller(pullers)


def generate_xray_event_file_consumer(output_dir: str) -> ObservabilityEventConsumer:
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


def generate_xray_event_console_consumer() -> ObservabilityEventConsumer:
    """
    Generates an instance of event consumer which will print events into console

    Returns
    -------
        Console consumer instance with desired mapper configuration
    """
    return ObservabilityEventConsumerDecorator([XRayTraceConsoleMapper()], XRayTraceConsoleConsumer())


def generate_xray_event_consumer(output_dir: Optional[str] = None) -> ObservabilityEventConsumer:
    """
    Generates consumer instance with the given variables.
    If output directory have been provided, then it will return file consumer.
    If not, it will return console consumer
    """
    if output_dir:
        return generate_xray_event_file_consumer(output_dir)
    return generate_xray_event_console_consumer()


def generate_xray_service_graph_file_consumer(output_dir: str) -> ObservabilityEventConsumer:
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
    return ObservabilityEventConsumerDecorator([XRayServiceGraphFileMapper()], XRayEventFileConsumer(output_dir))


def generate_xray_service_graph_console_consumer() -> ObservabilityEventConsumer:
    """
    Generates an instance of event consumer which will print events into console

    Returns
    -------
        Console consumer instance with desired mapper configuration
    """
    return ObservabilityEventConsumerDecorator([XRayServiceGraphConsoleMapper()], XRayTraceConsoleConsumer())


def generate_xray_service_graph_consumer(output_dir: Optional[str] = None) -> ObservabilityEventConsumer:
    """
    Generates consumer instance with the given variables.
    If output directory have been provided, then it will return file consumer.
    If not, it will return console consumer
    """
    if output_dir:
        return generate_xray_service_graph_file_consumer(output_dir)
    return generate_xray_service_graph_console_consumer()
