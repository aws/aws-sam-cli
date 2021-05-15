"""
Interfaces and generic implementations for observability events (like CW logs)
"""
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional, Generic, TypeVar, Any

LOG = logging.getLogger(__name__)

# Generic type for the internal observability event
InternalEventType = TypeVar("InternalEventType")


class ObservabilityEvent(Generic[InternalEventType]):
    """
    Generic class that represents observability event
    This keeps some common fields for filtering or sorting later on
    """

    def __init__(self, event: InternalEventType, timestamp: int, resource_name: Optional[str] = None):
        """
        Parameters
        ----------
        event : EventType
            Actual event object. This can be any type with generic definition (dict, str etc.)
        timestamp : int
            Timestamp of the event
        resource_name : Optional[str]
            Resource name related to this event. This is optional since not all events is connected to a single resource
        """
        self.event = event
        self.timestamp = timestamp
        self.resource_name = resource_name


# Generic type for identifying different ObservabilityEvent
ObservabilityEventType = TypeVar("ObservabilityEventType", bound=ObservabilityEvent)


class ObservabilityPuller(ABC):
    """
    Interface definition for pulling observability information.
    """

    @abstractmethod
    def tail(self, start_time: Optional[datetime] = None, filter_pattern: Optional[str] = None):
        """
        Parameters
        ----------
        start_time : Optional[datetime]
            Optional parameter to tail information from earlier time
        filter_pattern :  Optional[str]
            Optional parameter to filter events with given string
        """

    @abstractmethod
    def load_time_period(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        filter_pattern: Optional[str] = None,
    ):
        """
        Parameters
        ----------
        start_time : Optional[datetime]
            Optional parameter to load events from certain date time
        end_time :  Optional[datetime]
            Optional parameter to load events until certain date time
        filter_pattern : Optional[str]
            Optional parameter to filter events with given string
        """


# pylint: disable=fixme
# fixme add ABC parent class back once we bump the pylint to a version 2.8.2 or higher
class ObservabilityEventMapper(Generic[ObservabilityEventType]):
    """
    Interface definition to map/change any event to another object
    This could be used by highlighting certain parts or formatting events before logging into console
    """

    @abstractmethod
    def map(self, event: ObservabilityEventType) -> Any:
        """
        Parameters
        ----------
        event : ObservabilityEventType
            Event object that will be mapped/converted to another event or any object

        Returns
        -------
        Any
            Return converted type
        """


class ObservabilityEventConsumer(Generic[ObservabilityEventType]):
    """
    Consumer interface, which will consume any event.
    An example is to output event into console.
    """

    @abstractmethod
    def consume(self, event: ObservabilityEventType):
        """
        Parameters
        ----------
        event : ObservabilityEvent
            Event that will be consumed
        """


class ObservabilityEventConsumerDecorator(ObservabilityEventConsumer):
    """
    A decorator implementation for consumer, which can have mappers and decorated consumer within.
    Rather than the normal implementation, this will process the events through mappers which is been
    provided, and then pass them to actual consumer
    """

    def __init__(self, mappers: List[ObservabilityEventMapper], consumer: ObservabilityEventConsumer):
        """
        Parameters
        ----------
        mappers : List[ObservabilityEventMapper]
            List of event mappers which will be used to process events before passing to consumer
        consumer : ObservabilityEventConsumer
            Actual consumer which will handle the events after they are processed by mappers
        """
        super().__init__()
        self._mappers = mappers
        self._consumer = consumer

    def consume(self, event: ObservabilityEvent):
        """
        See Also ObservabilityEventConsumerDecorator and ObservabilityEventConsumer
        """
        for mapper in self._mappers:
            LOG.debug("Calling mapper (%s) for event (%s)", mapper, event)
            event = mapper.map(event)
        LOG.debug("Calling consumer (%s) for event (%s)", self._consumer, event)
        self._consumer.consume(event)
