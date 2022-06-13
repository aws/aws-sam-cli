"""
Represents Events and their values.
"""

from enum import Enum
from typing import List


class EventName(Enum):
    """Enum for the names of available events to track."""

    USED_FEATURE = "UsedFeature"
    DEPLOY = "Deploy"
    BUILD_RUNTIME = "BuildRuntime"


class EventType:
    """Class for Events and the types of values they may have."""

    _events = {
        EventName.USED_FEATURE: [
            "ESBuild",
            "Accelerate",
            "LocalTest",
            "CDK",
        ],
        EventName.DEPLOY: [
            "CreateChangeSetStart",
            "CreateChangeSetInProgress",
            "CreateChangeSetFailed",
            "CreateChangeSetSuccess",
        ],
    }

    @staticmethod
    def get_accepted_values(event_name: EventName) -> List[str]:
        """Get all acceptable values for a given Event."""
        if event_name not in EventType._events:
            return []
        return EventType._events[event_name]


class Event:
    """Class to represent Events that occur in SAM CLI."""

    event_name: EventName
    event_value: str  # Validated by EventType.get_accepted_values to never be an arbitrary string

    def __init__(self, event_name: str, event_value: str):
        Event._verify_event(event_name, event_value)
        self.event_name = EventName(event_name)
        self.event_value = event_value

    def __eq__(self, other):
        return self.event_name == other.event_name and self.event_value == other.event_value

    @staticmethod
    def _verify_event(event_name: str, event_value: str) -> None:
        """Raise an EventCreationError if either the event name or value is not valid."""
        if event_name not in Event._get_event_names():
            raise EventCreationError(f"Event '{event_name}' does not exist.")
        if event_value not in EventType.get_accepted_values(EventName(event_name)):
            raise EventCreationError(f"Event '{event_name}' does not accept value '{event_value}'.")

    @staticmethod
    def _get_event_names() -> List[str]:
        """Retrieves a list of all valid event names."""
        return [event.value for event in EventName]


class EventCreationError(Exception):
    """Exception called when an Event is not properly created."""
