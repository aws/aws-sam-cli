"""
Represents Events and their values.
"""

from datetime import datetime
from enum import Enum
import logging
import threading
from typing import List

from samcli.lib.telemetry.telemetry import Telemetry
from samcli.local.common.runtime_template import INIT_RUNTIMES


LOG = logging.getLogger(__name__)


class EventName(Enum):
    """Enum for the names of available events to track."""

    USED_FEATURE = "UsedFeature"
    BUILD_FUNCTION_RUNTIME = "BuildFunctionRuntime"
    SYNC_USED = "SyncUsed"
    SYNC_FLOW_START = "SyncFlowStart"
    SYNC_FLOW_END = "SyncFlowEnd"
    WORKFLOW_LANGUAGE = "WorkflowLanguage"
    WORKFLOW_DEPENDENCY_MANAGER = "WorkflowDependencyManager"


class EventType:
    """Class for Events and the types of values they may have."""

    _SYNC_FLOWS = [
        "AliasVersionSyncFlow",
        "AutoDependencyLayerSyncFlow",
        "AutoDependencyLayerParentSyncFlow",
        "FunctionSyncFlow",
        "FunctionLayerReferenceSync",
        "GenericApiSyncFlow",
        "HttpApiSyncFlow",
        "ImageFunctionSyncFlow",
        "LayerSyncFlow",
        "RestApiSyncFlow",
        "StepFunctionsSyncFlow",
        "ZipFunctionSyncFlow",
    ]
    _WORKFLOW_LANGUAGES = [
        "python",
        "nodejs",
        "ruby",
        "java",
        "dotnet",
        "go",
        "provided",
    ]
    _WORKFLOW_DEPENDENCY_MANAGERS = [
        "pip",
        "npm",
        "bundler",
        "gradle",
        "maven",
        "cli-package",
        "modules",
        "npm-esbuild",
    ]
    _events = {
        EventName.USED_FEATURE: [
            "ESBuild",
            "Accelerate",
            "CDK",
        ],
        EventName.BUILD_FUNCTION_RUNTIME: INIT_RUNTIMES,
        EventName.SYNC_USED: [
            "Start",
            "End",
        ],
        EventName.SYNC_FLOW_START: _SYNC_FLOWS,
        EventName.SYNC_FLOW_END: _SYNC_FLOWS,
        EventName.WORKFLOW_LANGUAGE: _WORKFLOW_LANGUAGES,
        EventName.WORKFLOW_DEPENDENCY_MANAGER: _WORKFLOW_DEPENDENCY_MANAGERS,
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
    thread_id = threading.get_ident()  # The thread ID; used to group Events from the same command run
    time_stamp: str

    def __init__(self, event_name: str, event_value: str):
        Event._verify_event(event_name, event_value)
        self.event_name = EventName(event_name)
        self.event_value = event_value
        self.time_stamp = str(datetime.utcnow())[:-3]  # format microseconds from 6 -> 3 figures to allow SQL casting

    def __eq__(self, other):
        return self.event_name == other.event_name and self.event_value == other.event_value

    def __repr__(self):
        return (
            f"Event(event_name={self.event_name.value}, "
            f"event_value={self.event_value}, "
            f"thread_id={self.thread_id}, "
            f"time_stamp={self.time_stamp})"
        )

    def to_json(self):
        return {
            "event_name": self.event_name.value,
            "event_value": self.event_value,
            "thread_id": self.thread_id,
            "time_stamp": self.time_stamp,
        }

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
    _event_lock = threading.Lock()

    MAX_EVENTS: int = 50  # Maximum number of events to store before sending

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
            should_send: bool = False
            with EventTracker._event_lock:
                EventTracker._events.append(Event(event_name, event_value))
                if len(EventTracker._events) >= EventTracker.MAX_EVENTS:
                    should_send = True
            if should_send:
                send_thread = threading.Thread(target=EventTracker.send_events)
                send_thread.start()
        except EventCreationError as e:
            LOG.debug("Error occurred while trying to track an event: %s", e)

    @staticmethod
    def get_tracked_events() -> List[Event]:
        with EventTracker._event_lock:
            return EventTracker._events

    @staticmethod
    def clear_trackers():
        """Clear the current list of tracked Events before the next session."""
        with EventTracker._event_lock:
            EventTracker._events = []

    @staticmethod
    def send_events():
        """Sends the current list of events via Telemetry."""
        from samcli.lib.telemetry.metric import Metric  # pylint: disable=cyclic-import

        with EventTracker._event_lock:
            if not EventTracker._events:  # Don't do anything if there are no events to send
                return

            telemetry = Telemetry()

            metric = Metric("events")
            msa = {}
            msa["events"] = [e.to_json() for e in EventTracker._events]
            metric.add_data("metricSpecificAttributes", msa)
            telemetry.emit(metric)
            EventTracker._events = []  # Manual clear_trackers() since we're within the lock


def track_long_event(start_event_name: str, start_event_value: str, end_event_name: str, end_event_value: str):
    """Decorator for tracking events that occur at start and end of a function.

    The decorator tracks two Events total, where the first Event occurs
    at the start of the decorated function's execution (prior to its
    first line) and the second Event occurs after the function has ended
    (after the final line of the function has executed).

    Parameters
    ----------
    start_event_name: str
        The name of the Event that is executed at the start of the
        decorated function's execution. Must be a valid EventName
        value or the decorator will not run.
    start_event_value: str
        The value of the Event that is executed at the start of the
        decorated function's execution. Must be a valid EventType
        value for the passed `start_event_name` or the decorator
        will not run.
    end_event_name: str
        The name of the Event that is executed at the end of the
        decorated function's execution. Must be a valid EventName
        value or the decorator will not run.
    end_event_value: str
        The value of the Event that is executed at the end of the
        decorated function's execution. Must be a valid EventType
        value for the passed `end_event_name` or the decorator
        will not run.

    Examples
    --------
    >>> @track_long_event("FuncStart", "Func1", "FuncEnd", "Func1")
        def func1(...):
            # do things

    >>> @track_long_event("FuncStart", "Func2", "FuncEnd", "Func2")
        def func2(...):
            # do things
    """
    should_track = True
    try:
        # Check that passed values are valid Events
        Event(start_event_name, start_event_value)
        Event(end_event_name, end_event_value)
    except EventCreationError as e:
        LOG.debug("Error occurred while trying to track an event: %s\nDecorator not run.", e)
        should_track = False

    def decorator_for_events(func):
        """The actual decorator"""

        def wrapped(*args, **kwargs):
            if should_track:
                EventTracker.track_event(start_event_name, start_event_value)
            exception = None

            try:
                return_value = func(*args, **kwargs)
            except Exception as e:
                exception = e

            if should_track:
                EventTracker.track_event(end_event_name, end_event_value)
                EventTracker.send_events()  # Ensure Events are sent at the end of execution
            if exception:
                raise exception

            return return_value

        return wrapped

    return decorator_for_events


class EventCreationError(Exception):
    """Exception called when an Event is not properly created."""
