"""
Shared formatting utilities for SAM CLI durable functions.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Union

from samcli.commands._utils.options import generate_next_command_recommendation

LOG = logging.getLogger(__name__)

# Truncation constants for table format
MAX_FIELD_LENGTH = 100
MAX_FIELD_LENGTH_WITH_ERROR = 60  # Shorter limit when both Payload and Error columns present
TRUNCATION_SUFFIX = "..."


def truncate_field(value: str, max_length: int = MAX_FIELD_LENGTH) -> tuple[str, bool]:
    """Truncate field value if it exceeds max_length, showing partial content.

    Returns:
        tuple: (truncated_value, was_truncated)
    """
    # Try to compress JSON for better readability
    try:
        parsed = json.loads(value)
        compressed = json.dumps(parsed, separators=(",", ":"))
    except (json.JSONDecodeError, TypeError):
        compressed = value

    if len(compressed) <= max_length:
        return compressed, False
    # Show first part of the value with ellipsis
    truncate_at = max_length - len(TRUNCATION_SUFFIX)
    return f"{compressed[:truncate_at]}{TRUNCATION_SUFFIX}", True


def format_timestamp(timestamp) -> str:
    """Format timestamp to human-readable format."""
    if not timestamp:
        return "-"
    try:
        return str(timestamp.strftime("%H:%M:%S"))
    except (ValueError, AttributeError, OSError):
        return str(timestamp)


def clean_response_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Clean AWS API response data by stripping ResponseMetadata."""
    cleaned_data = data.copy()
    cleaned_data.pop("ResponseMetadata", None)
    return cleaned_data


def format_execution_history(history_result: Dict[str, Any], format: str = "table", execution_arn: str = "") -> str:
    """Get execution history in the requested format."""
    cleaned_result = clean_response_data(history_result)

    if format == "json":
        return json.dumps(cleaned_result, indent=2, default=str)
    else:  # table (default)
        return format_execution_history_table(cleaned_result, execution_arn)


def format_execution_details(execution_arn: str, execution_details: Dict[str, Any], format: str = "summary") -> str:
    """Get execution details in the requested format."""
    cleaned_details = clean_response_data(execution_details)

    if format == "json":
        return json.dumps(cleaned_details, indent=2, default=str)
    else:  # summary (default)
        return format_execution_details_summary(execution_arn, cleaned_details)


def format_execution_details_summary(execution_arn: str, execution_details: Dict[str, Any]) -> str:
    """Get execution details in summary format."""
    # Calculate duration
    start_time = execution_details.get("StartTimestamp")
    end_time = execution_details.get("EndTimestamp")
    duration = "N/A"
    if start_time and end_time:
        duration_seconds = (end_time - start_time).total_seconds()
        duration = f"{duration_seconds:.2f}s"

    # Determine status with emoji
    status = execution_details.get("Status", "UNKNOWN")
    if status == "SUCCEEDED":
        status_display = "SUCCEEDED ✅"
    elif status == "FAILED":
        status_display = "FAILED ❌"
    elif status in ["TIMED_OUT", "STOPPED"]:
        status_display = f"{status} ⚠️"
    else:
        status_display = status

    # Get basic execution info
    input_data = execution_details.get("InputPayload", "N/A")
    execution_name = execution_details.get("DurableExecutionName", "N/A")

    # Build the base summary
    summary = f"""
Execution Summary:
=========================
ARN:      {execution_arn}
Name:     {execution_name}
Duration: {duration}
Status:   {status_display}
Input:    {input_data}"""

    # Add result if present
    if "Result" in execution_details:
        summary += f"""
Result:   {execution_details["Result"]}"""

    # Add error information if present
    if "Error" in execution_details:
        error = execution_details["Error"]
        error_message = error.get("ErrorMessage", "Unknown error")
        error_type = error.get("ErrorType", "Unknown")
        summary += f"""
Error:    {error_type}: {error_message}"""

    return summary


def format_event_details(event: Dict[str, Any]) -> str:
    """Format event-specific details based on event type."""
    event_type = event.get("EventType", "")

    if event_type == "ExecutionStarted":
        details = event.get("ExecutionStartedDetails", {})
        timeout = details.get("ExecutionTimeout")
        return f"Timeout: {timeout}s" if timeout else ""

    elif event_type == "WaitStarted":
        details = event.get("WaitStartedDetails", {})
        duration = details.get("Duration")
        return f"Duration: {duration}s" if duration else ""

    elif event_type == "CallbackStarted":
        details = event.get("CallbackStartedDetails", {})
        timeout = details.get("Timeout")
        heartbeat_timeout = details.get("HeartbeatTimeout")
        parts = []
        if timeout:
            parts.append(f"Timeout: {timeout}s")
        if heartbeat_timeout:
            parts.append(f"Heartbeat: {heartbeat_timeout}s")
        return ", ".join(parts)

    elif event_type == "StepSucceeded":
        details = event.get("StepSucceededDetails", {})
        retry_details = details.get("RetryDetails", {})
        current_attempt = retry_details.get("CurrentAttempt")
        if current_attempt:
            retries_attempted = current_attempt - 1
            if retries_attempted > 0:
                return f"Retries Attempted: {retries_attempted}"
        return ""

    elif event_type == "InvocationCompleted":
        details = event.get("InvocationCompletedDetails", {})
        request_id = details.get("RequestId")
        return f"Invocation Id: {request_id}" if request_id else ""

    elif event_type == "ExecutionTimedOut":
        details = event.get("ExecutionTimedOutDetails", {})
        error = details.get("Error")
        return f"Error: {error}" if error else "Execution exceeded timeout"

    return ""


def format_event_result(event: Dict[str, Any], has_errors: bool = False) -> tuple[str, bool]:
    """Extract and format result/payload data from event.

    Returns:
        tuple: (formatted_result, was_truncated)
    """
    event_type = event.get("EventType", "")
    max_length = MAX_FIELD_LENGTH_WITH_ERROR if has_errors else MAX_FIELD_LENGTH

    # Map event types to their detail keys and data keys
    event_config = {
        "ExecutionStarted": ("ExecutionStartedDetails", "Input"),
        "StepSucceeded": ("StepSucceededDetails", "Result"),
        "InvocationCompleted": ("InvocationCompletedDetails", "Result"),
        "ExecutionSucceeded": ("ExecutionSucceededDetails", "Result"),
        "CallbackSucceeded": ("CallbackSucceededDetails", "Result"),
        "ChainedInvokeSucceeded": ("ChainedInvokeSucceededDetails", "Result"),
        "ContextSucceeded": ("ContextSucceededDetails", "Result"),
    }

    if event_type in event_config:
        details_key, data_key = event_config[event_type]
        details = event.get(details_key, {})
        data = details.get(data_key)

        # If data is a dict with Payload key, extract just the Payload
        if data and isinstance(data, dict):
            if "Payload" in data:
                return truncate_field(str(data["Payload"]), max_length)
            # If it's a dict without Payload, return empty (it's just metadata like Truncated)
            return "-", False

        # If data is a simple value (string, number, etc), return it
        if data:
            return truncate_field(str(data), max_length)
        return "-", False

    return "-", False


def _extract_error(event: Dict[str, Any]) -> tuple[Optional[str], bool]:
    """Extract error information from an event if present.

    Returns:
        tuple: (error_message, was_truncated)
    """
    event_type = event.get("EventType", "")

    # Map event types that can have errors to their detail keys
    error_event_types = {
        "ExecutionFailed": "ExecutionFailedDetails",
        "ExecutionTimedOut": "ExecutionTimedOutDetails",
        "ExecutionStopped": "ExecutionStoppedDetails",
        "ContextFailed": "ContextFailedDetails",
        "StepFailed": "StepFailedDetails",
        "ChainedInvokeFailed": "ChainedInvokeFailedDetails",
        "ChainedInvokeTimedOut": "ChainedInvokeTimedOutDetails",
        "ChainedInvokeStopped": "ChainedInvokeStoppedDetails",
        "CallbackFailed": "CallbackFailedDetails",
        "CallbackTimedOut": "CallbackTimedOutDetails",
        "InvocationCompleted": "InvocationCompletedDetails",
    }

    if event_type in error_event_types:
        details_key = error_event_types[event_type]
        details = event.get(details_key, {})
        error = details.get("Error")

        if isinstance(error, dict):
            error_payload = error.get("Payload")
            if isinstance(error_payload, dict):
                error_type = error_payload.get("ErrorType", "")
                error_message = error_payload.get("ErrorMessage", "")
                if error_type and error_message:
                    return truncate_field(f"{error_type}: {error_message}", MAX_FIELD_LENGTH_WITH_ERROR)
                error_str = error_type or error_message
                if error_str:
                    return truncate_field(error_str, MAX_FIELD_LENGTH_WITH_ERROR)
                return None, False

    return None, False


def format_execution_history_table(history_data: Dict[str, Any], execution_arn: str) -> str:
    """Format execution history data into a table."""
    events = history_data.get("Events", [])
    if not events:
        return "No execution events found."

    # Check if any event has an error
    has_errors = any(_extract_error(event)[0] for event in events)
    any_truncated = False

    rows = []
    for event in events:
        payload, payload_truncated = format_event_result(event, has_errors)
        any_truncated = any_truncated or payload_truncated

        row = {
            "Event Id": event.get("EventId") or "-",
            "Event Type": event.get("EventType") or "-",
            "SubType": event.get("SubType") or "-",
            "Name": event.get("Name") or "-",
            "Timestamp": format_timestamp(event.get("EventTimestamp")),
            "Details": format_event_details(event) or "-",
            "Payload": payload,
        }
        if has_errors:
            error, error_truncated = _extract_error(event)
            any_truncated = any_truncated or error_truncated
            row["Error"] = error or "-"
        rows.append(row)

    table = _create_table(rows, has_errors)

    # Add truncation note if any fields were truncated
    if any_truncated:
        table += (
            f"\n\nNote: Some fields were truncated. "
            f"Use 'sam local execution history {execution_arn} --format json' to view full output."
        )

    return table


def _create_table(rows: List[Dict[str, Union[str, int]]], has_errors: bool = False) -> str:
    """Create ASCII table from rows."""
    if not rows:
        return ""

    headers = ["Event Id", "Event Type", "SubType", "Name", "Timestamp", "Details", "Payload"]
    if has_errors:
        headers.append("Error")

    # Calculate column widths
    widths = {}
    for header in headers:
        widths[header] = len(header)
        for row in rows:
            value = row.get(header, "")
            if isinstance(value, int):
                value = str(value)
            widths[header] = max(widths[header], len(value))

    # Create table
    lines = []

    # Header row
    header_line = "│ " + " │ ".join(h.center(widths[h]) for h in headers) + " │"
    lines.append("┌" + "┬".join("─" * (widths[h] + 2) for h in headers) + "┐")
    lines.append(header_line)
    lines.append("├" + "┼".join("─" * (widths[h] + 2) for h in headers) + "┤")

    # Data rows
    for row in rows:
        data_line = (
            "│ "
            + " │ ".join(
                (
                    str(row.get(h, "")).ljust(widths[h])
                    if h in ["Details", "Payload", "Error"]
                    else str(row.get(h, "")).center(widths[h])
                )
                for h in headers
            )
            + " │"
        )
        lines.append(data_line)

    lines.append("└" + "┴".join("─" * (widths[h] + 2) for h in headers) + "┘")

    return "\n".join(lines)


def format_next_commands_after_invoke(execution_arn: str) -> str:
    """Format next command suggestions."""
    return generate_next_command_recommendation(
        [
            ("Get execution details", f"sam local execution get {execution_arn}"),
            ("View execution history", f"sam local execution history {execution_arn}"),
        ]
    )


def format_callback_success_message(callback_id: str, result: Optional[str] = None) -> str:
    """Get formatted success message for callback operations."""
    message = f"✅ Callback success sent for ID: {callback_id}"
    if result:
        message += f"\nResult: {result}"
    return message


def format_callback_failure_message(
    callback_id: str,
    error_data: Optional[str] = None,
    error_type: Optional[str] = None,
    error_message: Optional[str] = None,
) -> str:
    """Get formatted success message for callback failure operations."""
    message = f"❌ Callback failure sent for ID: {callback_id}"
    if error_type:
        message += f"\nError Type: {error_type}"
    if error_message:
        message += f"\nError Message: {error_message}"
    if error_data:
        message += f"\nError Data: {error_data}"
    return message


def format_callback_heartbeat_message(callback_id: str) -> str:
    """Get formatted success message for callback heartbeat operations."""
    return f"💓 Callback heartbeat sent for ID: {callback_id}"


def format_stop_execution_message(
    execution_arn: str,
    error_type: Optional[str] = None,
    error_message: Optional[str] = None,
    error_data: Optional[str] = None,
) -> str:
    """Get formatted success message for execution stop operations."""
    message = f"🛑 Execution stopped: {execution_arn}"
    if error_type:
        message += f"\nError Type: {error_type}"
    if error_message:
        message += f"\nError Message: {error_message}"
    if error_data:
        message += f"\nError Data: {error_data}"
    return message
