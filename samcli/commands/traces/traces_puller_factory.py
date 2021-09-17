"""
Factory methods which generates puller and consumer instances for XRay events
"""
from typing import Any, List

from samcli.commands.traces.trace_console_consumers import XRayTraceConsoleConsumer
from samcli.lib.observability.observability_info_puller import (
    ObservabilityPuller,
    ObservabilityEventConsumer,
    ObservabilityEventConsumerDecorator,
    ObservabilityCombinedPuller,
)
from samcli.lib.observability.xray_traces.xray_event_mappers import (
    XRayTraceConsoleMapper,
    XRayServiceGraphConsoleMapper,
    XRayServiceGraphJSONMapper,
    XRayTraceJSONMapper,
)
from samcli.lib.observability.xray_traces.xray_event_puller import XRayTracePuller
from samcli.lib.observability.xray_traces.xray_service_graph_event_puller import XRayServiceGraphPuller


def generate_trace_puller(
    xray_client: Any,
    unformatted: bool = False,
) -> ObservabilityPuller:
    """
    Generates puller instance with correct consumer and/or mapper configuration

    Parameters
    ----------
    xray_client : Any
        boto3 xray client to be used in XRayTracePuller instance
    unformatted : bool
        By default, logs and traces are printed with a format for terminal. If this option is provided, the events
        will be printed unformatted in JSON.

    Returns
    -------
        Puller instance with desired configuration
    """
    pullers: List[ObservabilityPuller] = []
    pullers.append(XRayTracePuller(xray_client, generate_xray_event_consumer(unformatted)))
    pullers.append(XRayServiceGraphPuller(xray_client, generate_xray_service_graph_consumer(unformatted)))

    return ObservabilityCombinedPuller(pullers)


def generate_unformatted_xray_event_consumer() -> ObservabilityEventConsumer:
    """
    Generates unformatted consumer, which will print XRay events unformatted JSON into terminal

    Returns
    -------
        File consumer instance with desired mapper configuration
    """
    return ObservabilityEventConsumerDecorator([XRayTraceJSONMapper()], XRayTraceConsoleConsumer())


def generate_xray_event_console_consumer() -> ObservabilityEventConsumer:
    """
    Generates an instance of event consumer which will print events into console

    Returns
    -------
        Console consumer instance with desired mapper configuration
    """
    return ObservabilityEventConsumerDecorator([XRayTraceConsoleMapper()], XRayTraceConsoleConsumer())


def generate_xray_event_consumer(unformatted: bool = False) -> ObservabilityEventConsumer:
    """
    Generates consumer instance with the given variables.
    If unformatted is True, then it will return consumer with formatters for just JSON.
    If not, it will return console consumer
    """
    if unformatted:
        return generate_unformatted_xray_event_consumer()
    return generate_xray_event_console_consumer()


def generate_unformatted_xray_service_graph_consumer() -> ObservabilityEventConsumer:
    """
    Generates unformatted consumer, which will print XRay events unformatted JSON into terminal

    Returns
    -------
        File consumer instance with desired mapper configuration
    """
    return ObservabilityEventConsumerDecorator([XRayServiceGraphJSONMapper()], XRayTraceConsoleConsumer())


def generate_xray_service_graph_console_consumer() -> ObservabilityEventConsumer:
    """
    Generates an instance of event consumer which will print events into console

    Returns
    -------
        Console consumer instance with desired mapper configuration
    """
    return ObservabilityEventConsumerDecorator([XRayServiceGraphConsoleMapper()], XRayTraceConsoleConsumer())


def generate_xray_service_graph_consumer(unformatted: bool = False) -> ObservabilityEventConsumer:
    """
    Generates consumer instance with the given variables.
    If unformatted is True, then it will return consumer with formatters for just JSON.
    If not, it will return console consumer
    """
    if unformatted:
        return generate_unformatted_xray_service_graph_consumer()
    return generate_xray_service_graph_console_consumer()
