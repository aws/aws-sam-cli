"""
Represents Events and their values.
"""

from enum import Enum
import logging
from typing import List

from samcli.local.common.runtime_template import INIT_RUNTIMES


LOG = logging.getLogger(__name__)

class EventName(Enum):
    """Enum for the names of available events to track."""

    USED_FEATURE = "UsedFeature"
    DEPLOY = "Deploy"
    BUILD_FUNCTION_RUNTIME = "BuildFunctionRuntime"


class EventType:
    """Class for Events and the types of values they may have."""

    _events = {
        EventName.USED_FEATURE: [
            "ESBuild",
            "Accelerate",
            "CDK",
        ],
        EventName.DEPLOY: [
            "CreateChangeSetStart",
            "CreateChangeSetInProgress",
            "CreateChangeSetFailed",
            "CreateChangeSetSuccess",
        ],
        EventName.BUILD_FUNCTION_RUNTIME: INIT_RUNTIMES,
    }

    @staticmethod
    def get_accepted_values(event_name: EventName) -> List[str]:
        """Get all acceptable values for a given Event name."""
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

    def __repr__(self):
        return f"Event(event_name={self.event_name.value}, event_value={self.event_value})"

    def to_json(self):
        return {"event_name": self.event_name.value, "event_value": self.event_value}

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


class EventTracker:
    """Class to track and recreate Events as they occur."""

    _events: List[Event] = []

    @staticmethod
    def track_event(event_name: str, event_value: str):
        """Method to track an event where and when it occurs.

        Place this method in the codepath of the event that you would
        like to track. For instance, if you would like to track when
        FeatureX is used, append this method to the end of that function.

        Parameters
        ----------
        event_name: str
            The name of the Event. Must be a valid EventName value, or an
            EventCreationError will be thrown.
        event_value: str
            The value of the Event. Must be a valid EventType value for the
            passed event_name, or an EventCreationError will be thrown.

        Examples
        --------
        >>> def feature_x(...):
                # do things
                EventTracker.track_event("UsedFeature", "FeatureX")

        >>> def feature_y(...) -> Any:
                # do things
                EventTracker.track_event("UsedFeature", "FeatureY")
                return some_value
        """
        try:
            EventTracker._events.append(Event(event_name, event_value))
        except EventCreationError as e:
            LOG.error(f"Error occurred while trying to track an event: {e}")

    @staticmethod
    def get_tracked_events() -> List[Event]:
        return EventTracker._events

    @staticmethod
    def clear_trackers():
        """Clear the current list of tracked Events before the next session."""
        EventTracker._events = []


class EventCreationError(Exception):
    """Exception called when an Event is not properly created."""
