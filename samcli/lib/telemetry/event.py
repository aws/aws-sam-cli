"""
Represents Events and their values.
"""

from abc import ABC
from enum import Enum
from typing import Any, List


class EventName(Enum):
    """Enum for the names of available events to track."""

    USED_FEATURE = "UsedFeature"
    DEPLOY = "Deploy"
    BUILD_RUNTIME = "BuildRuntime"


class EventType(ABC):
    """Abstract class for Events and the types of values they may have."""

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
        Event._verify_event_name(event_name)
        self.event_name = EventName(event_name)
        if event_value not in EventType.get_accepted_values(self.event_name):
            raise KeyError(f"Event '{self.event_name.value}' does not accept value '{event_value}'.")
        self.event_value = event_value

    def __eq__(self, other):
        return self.event_name == other.event_name and self.event_value == other.event_value

    @staticmethod
    def _verify_event_name(event_name: Any) -> None:
        """Raise a NameError if the passed parameter is not an EventName Enum."""
        if event_name not in [event.value for event in EventName]:
            raise NameError(f"Event '{event_name}' does not exist.")
