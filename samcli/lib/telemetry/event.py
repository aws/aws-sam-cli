"""
Represents Events and their values.
"""

import logging
import threading
from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID, uuid4

from samcli.cli.context import Context
from samcli.lib.build.workflows import ALL_CONFIGS
from samcli.lib.config.file_manager import FILE_MANAGER_MAPPER
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
    BUILD_WORKFLOW_USED = "BuildWorkflowUsed"
    CONFIG_FILE_EXTENSION = "SamConfigFileExtension"


class UsedFeature(Enum):
    """Enum for the names of event values of UsedFeature"""

    ACCELERATE = "Accelerate"
    CDK = "CDK"
    INIT_WITH_APPLICATION_INSIGHTS = "InitWithApplicationInsights"
    CFNLint = "CFNLint"
    INVOKED_CUSTOM_LAMBDA_AUTHORIZERS = "InvokedLambdaAuthorizers"


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
        "InfraSyncExecute",
        "SkipInfraSyncExecute",
    ]
    _WORKFLOWS = [f"{config.language}-{config.dependency_manager}" for config in ALL_CONFIGS]

    _event_values = {  # Contains allowable values for Events
        EventName.USED_FEATURE: [event.value for event in UsedFeature],
        EventName.BUILD_FUNCTION_RUNTIME: INIT_RUNTIMES,
        EventName.SYNC_USED: [
            "Start",
            "End",
        ],
        EventName.SYNC_FLOW_START: _SYNC_FLOWS,
        EventName.SYNC_FLOW_END: _SYNC_FLOWS,
        EventName.BUILD_WORKFLOW_USED: _WORKFLOWS,
        EventName.CONFIG_FILE_EXTENSION: list(FILE_MANAGER_MAPPER.keys()),
    }

    @staticmethod
    def get_accepted_values(event_name: EventName) -> List[str]:
        """Get all acceptable values for a given Event name."""
        if event_name not in EventType._event_values:
            return []
        return EventType._event_values[event_name]


class Event:
    """Class to represent Events that occur in SAM CLI."""

    event_name: EventName
    event_value: str  # Validated by EventType.get_accepted_values to never be an arbitrary string
    thread_id: Optional[UUID]  # The thread ID; used to group Events from the same command run
    time_stamp: str
    exception_name: Optional[str]

    def __init__(
        self, event_name: str, event_value: str, thread_id: Optional[UUID] = None, exception_name: Optional[str] = None
    ):
        Event._verify_event(event_name, event_value)
        self.event_name = EventName(event_name)
        self.event_value = event_value
        if not thread_id:
            thread_id = uuid4()
        self.thread_id = thread_id
        self.time_stamp = str(datetime.utcnow())[:-3]  # format microseconds from 6 -> 3 figures to allow SQL casting
        self.exception_name = exception_name

    def __eq__(self, other):
        return (
            self.event_name == other.event_name
            and self.event_value == other.event_value
            and self.exception_name == other.exception_name
        )

    def __repr__(self):
        return (
            f"Event(event_name={self.event_name.value}, "
            f"event_value={self.event_value}, "
            f"thread_id={self.thread_id.hex}, "
            f"time_stamp={self.time_stamp})",
            f"exception_name={self.exception_name})",
        )

    def to_json(self):
        return {
            "event_name": self.event_name.value,
            "event_value": self.event_value,
            "thread_id": self.thread_id.hex,
            "time_stamp": self.time_stamp,
            "exception_name": self.exception_name,
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
    _session_id: Optional[str] = None

    MAX_EVENTS: int = 50  # Maximum number of events to store before sending

    @staticmethod
    def track_event(
        event_name: str,
        event_value: str,
        session_id: Optional[str] = None,
        thread_id: Optional[UUID] = None,
        exception_name: Optional[str] = None,
    ):
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
        session_id: Optional[str]
            The session ID to set to link back to the original command run
        thread_id: Optional[UUID]
            The thread ID of the Event to track, as a UUID.
        exception_name: Optional[str]
            The name of the exception that this event encountered when tracking a feature

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

        if session_id:
            EventTracker._session_id = session_id

        try:
            should_send: bool = False
            # Validate the thread ID
            if not thread_id:  # Passed value is not a UUID or None
                thread_id = uuid4()
            with EventTracker._event_lock:
                EventTracker._events.append(
                    Event(event_name, event_value, thread_id=thread_id, exception_name=exception_name)
                )

                # Get the session ID (needed for multithreading sending)
                EventTracker._set_session_id()

                if len(EventTracker._events) >= EventTracker.MAX_EVENTS:
                    should_send = True
            if should_send:
                EventTracker.send_events()
        except EventCreationError as e:
            LOG.debug("Error occurred while trying to track an event: %s", e)

    @staticmethod
    def get_tracked_events() -> List[Event]:
        """Retrieve a list of all currently tracked Events."""
        with EventTracker._event_lock:
            return EventTracker._events

    @staticmethod
    def clear_trackers():
        """Clear the current list of tracked Events before the next session."""
        with EventTracker._event_lock:
            EventTracker._events = []

    @staticmethod
    def send_events() -> threading.Thread:
        """Call a thread to send the current list of Events via Telemetry."""
        send_thread = threading.Thread(target=EventTracker._send_events_in_thread)
        send_thread.start()
        return send_thread

    @staticmethod
    def _set_session_id() -> None:
        """
        Get the session ID from click and save it locally.
        """
        if not EventTracker._session_id:
            try:
                ctx = Context.get_current_context()
                if ctx:
                    EventTracker._session_id = ctx.session_id
            except RuntimeError:
                LOG.debug("EventTracker: Unable to obtain session ID")

    @staticmethod
    def _send_events_in_thread():
        """Send the current list of Events via Telemetry."""
        from samcli.lib.telemetry.metric import Metric  # pylint: disable=cyclic-import

        msa = {}

        with EventTracker._event_lock:
            if not EventTracker._events:  # Don't do anything if there are no events to send
                return

            msa["events"] = [e.to_json() for e in EventTracker._events]
            EventTracker._events = []  # Manual clear_trackers() since we're within the lock

        telemetry = Telemetry()
        metric = Metric("events")
        metric.add_data("sessionId", EventTracker._session_id)
        metric.add_data("metricSpecificAttributes", msa)
        telemetry.emit(metric)


def track_long_event(
    start_event_name: str,
    start_event_value: str,
    end_event_name: str,
    end_event_value: str,
    thread_id: Optional[UUID] = None,
):
    """Decorator for tracking events that occur at start and end of a function.

    The decorator tracks two Events total, where the first Event occurs
    at the start of the decorated function's execution (prior to its
    first line) and the second Event occurs after the function has ended
    (after the final line of the function has executed).
    If this decorator is being placed in a function that also contains the
    `track_command` decorator, ensure that this decorator is placed BELOW
    `track_command`. Otherwise, the current list of Events will be sent
    before the end_event will be added, resulting in an additional 'events'
    metric with only that single Event.

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
    thread_id: Optional[UUID]
        The thread ID of the Events to track, as a UUID.

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
        # Validate the thread ID
        if not thread_id:  # Passed value is not a UUID or None
            thread_id = uuid4()
    except EventCreationError as e:
        LOG.debug("Error occurred while trying to track an event: %s\nDecorator not run.", e)
        should_track = False

    def decorator_for_events(func):
        """The actual decorator"""

        def wrapped(*args, **kwargs):
            # Track starting event
            if should_track:
                EventTracker.track_event(start_event_name, start_event_value, thread_id=thread_id)
            exception = None
            # Run the function
            try:
                return_value = func(*args, **kwargs)
            except Exception as e:
                exception = e
            # Track ending event
            if should_track:
                EventTracker.track_event(end_event_name, end_event_value, thread_id=thread_id)
                EventTracker.send_events()  # Ensure Events are sent at the end of execution
            if exception:
                raise exception

            return return_value

        return wrapped

    return decorator_for_events


class EventCreationError(Exception):
    """Exception called when an Event is not properly created."""
