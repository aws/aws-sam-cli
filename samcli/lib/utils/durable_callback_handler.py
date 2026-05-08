"""
Interactive callback handler for durable function executions.
"""

import logging
from typing import Optional

import click

from samcli.lib.clients.lambda_client import DurableFunctionsClient

LOG = logging.getLogger(__name__)

# Menu choice constants
CHOICE_SUCCESS = 1
CHOICE_FAILURE = 2
CHOICE_HEARTBEAT = 3
CHOICE_STOP = 4


class DurableCallbackHandler:
    """
    Handles interactive callback detection and response for durable executions.
    """

    def __init__(self, client: DurableFunctionsClient):
        self.client = client
        self._prompted_callbacks: set[str] = set()  # Track which callbacks we've already prompted for

    def check_for_pending_callbacks(self, execution_arn: str) -> Optional[str]:
        """
        Check execution history for pending callbacks.

        Returns:
            callback_id if found, None otherwise
        """
        try:
            LOG.debug("Checking for pending callbacks in execution: %s", execution_arn)
            history = self.client.get_durable_execution_history(execution_arn)
            events = history.get("Events", [])

            if events:
                callback_states = {}

                for event in events:
                    event_type = event.get("EventType")
                    event_id = event.get("Id")

                    if event_type == "CallbackStarted":
                        callback_id = event.get("CallbackStartedDetails", {}).get("CallbackId")
                        callback_states[event_id] = {"callback_id": callback_id, "status": "STARTED", "event": event}
                    elif event_type in ["CallbackCompleted", "CallbackFailed", "CallbackSucceeded"]:
                        if event_id in callback_states:
                            callback_states[event_id]["status"] = "COMPLETED"

                # Find callbacks that are started but not completed
                for callback_id, state in callback_states.items():
                    if state["status"] == "STARTED" and state["callback_id"]:
                        return str(state["callback_id"])

        except Exception as e:
            LOG.error("Failed to check callback history: %s", e)

        return None

    def prompt_callback_response(self, execution_arn: str, callback_id: str, execution_complete=None) -> bool:
        """
        Prompt user for callback response and send it.

        Args:
            execution_arn: The execution ARN for stop execution operation
            callback_id: The callback ID to respond to
            execution_complete: Optional threading.Event to check if execution finished

        Returns:
            True if callback was sent, False if user chose to continue waiting
        """
        # Only prompt once per callback ID to avoid blocking on timed-out callbacks
        if callback_id in self._prompted_callbacks:
            return False

        self._prompted_callbacks.add(callback_id)

        # Check if execution already completed before prompting
        if execution_complete and execution_complete.is_set():
            return False

        click.echo(f"\n🔄 Execution is waiting for callback: {callback_id}")
        click.echo("Choose an action:")
        click.echo("  1. Send callback success")
        click.echo("  2. Send callback failure")
        click.echo("  3. Send callback heartbeat")
        click.echo("  4. Stop execution")

        choice = click.prompt("Enter choice", type=click.IntRange(1, 4), default=CHOICE_SUCCESS)

        # Check again after user makes selection in case execution completed
        if execution_complete and execution_complete.is_set():
            click.echo("⚠️  Execution already completed, callback no longer needed")
            return False

        try:
            if choice == CHOICE_SUCCESS:
                result = click.prompt("Enter success result (optional)", default="", show_default=False)
                self.client.send_callback_success(callback_id=callback_id, result=result)
                click.echo("✅ Callback success sent")
                return True

            elif choice == CHOICE_FAILURE:
                error_message = click.prompt("Enter error message", default="User cancelled")
                error_type = click.prompt("Enter error type (optional)", default="", show_default=False) or None

                self.client.send_callback_failure(
                    callback_id=callback_id, error_message=error_message, error_type=error_type
                )
                click.echo("❌ Callback failure sent")
                return True

            elif choice == CHOICE_HEARTBEAT:
                self.client.send_callback_heartbeat(callback_id=callback_id)
                click.echo("💓 Callback heartbeat sent")
                return False  # Continue waiting after heartbeat

            else:  # CHOICE_STOP
                error_message = click.prompt("Enter error message", default="Execution stopped by user")
                error_type = click.prompt("Enter error type (optional)", default="", show_default=False) or None

                self.client.stop_durable_execution(
                    durable_execution_arn=execution_arn, error_message=error_message, error_type=error_type
                )
                click.echo("🛑 Execution stopped")
                return True

        except Exception as e:
            LOG.error("Failed to send callback: %s", e)
            click.echo(f"❌ Failed to send callback: {e}")
            return False
