"""
Represents Durable Lambda runtime containers.
"""

import logging
import threading
import time

import click
from flask import has_request_context

from samcli.lib.utils.durable_callback_handler import DurableCallbackHandler
from samcli.lib.utils.durable_formatters import format_execution_details, format_next_commands_after_invoke
from samcli.local.docker.lambda_container import LambdaContainer

LOG = logging.getLogger(__name__)


class DurableLambdaContainer(LambdaContainer):
    """
    Represents a Durable Lambda runtime container.
    Extends LambdaContainer to add durable execution support via an emulator container.
    """

    def __init__(self, *args, emulator_container, durable_config, is_warm_runtime=False, **kwargs):
        self.emulator_container = emulator_container
        self.durable_config = durable_config

        """
        Persist the runtime mode -- since we manage the lambda container lifecycle, 
        we need to adhere to the behaviour of the container modes for the HTTP service (cold, lazy, eager)
        """
        self._is_warm_runtime = is_warm_runtime

        self._update_lambda_environment_with_emulator_endpoint(kwargs)
        super().__init__(*args, **kwargs)

    def _is_cli_context(self):
        """
        Detect if we're running in CLI context vs HTTP service context.
        Returns True if running from CLI, False if running from HTTP service.
        """
        return not has_request_context()

    def _update_lambda_environment_with_emulator_endpoint(self, kwargs):
        """
        Set up environment variables for Lambda container to communicate with emulator.

        This is done by setting the AWS_ENDPOINT_URL_LAMBDA to be the emulator port, allowing
        calls from the customer code to CheckpointDurableExecution and GetDurableExecutionState
        to be routed to the emulator container.
        """
        env_vars = kwargs.get("env_vars", {}) or {}
        env_vars["AWS_ENDPOINT_URL_LAMBDA"] = f"http://host.docker.internal:{self.emulator_container.port}"
        kwargs["env_vars"] = env_vars

        # Add extra_hosts to allow Lambda container to resolve host.docker.internal
        extra_hosts = kwargs.get("extra_hosts") or {}
        extra_hosts["host.docker.internal"] = "host-gateway"
        kwargs["extra_hosts"] = extra_hosts

        # Bind to 0.0.0.0 so emulator can reach Lambda via host.docker.internal
        kwargs["container_host_interface"] = "0.0.0.0"

    def _get_lambda_container_endpoint(self):
        """
        Get the Lambda container endpoint URL for the emulator to invoke.
        Uses localhost for external emulator, host.docker.internal for containerized emulator.
        """
        lambda_host = "localhost" if self.emulator_container._is_external_emulator() else "host.docker.internal"
        return f"http://{lambda_host}:{self.get_port()}"

    def wait_for_result(
        self,
        full_path,
        event,
        stdout,
        stderr,
        start_timer=None,
        durable_execution_name=None,
        invocation_type="RequestResponse",
    ):
        """
        Override to handle durable execution flow.
        Returns headers dict with execution ARN for durable functions.
        """
        self.emulator_container.start_or_attach()
        self.start()

        self.start_logs_thread_if_not_alive(stderr)
        LOG.debug("Started logging thread for Lambda container on port %s", self.get_port())

        self._wait_for_socket_connection()

        LOG.debug("Starting durable execution")
        lambda_endpoint = self._get_lambda_container_endpoint()
        result = self.emulator_container.start_durable_execution(
            durable_execution_name, event, lambda_endpoint, self.durable_config
        )
        execution_arn = result.get("ExecutionArn")
        LOG.debug("Received execution ARN: %s", execution_arn)
        headers = {"X-Amz-Durable-Execution-Arn": execution_arn}

        if invocation_type == "Event":
            # For async invocations, start background thread and return immediately
            # Container cleanup will happen in the background thread
            def _wait_for_execution_completion():
                try:
                    self._wait_for_execution(execution_arn)
                except Exception as e:
                    LOG.error("Error in async execution completion: %s", e)

            completion_thread = threading.Thread(target=_wait_for_execution_completion, daemon=True)
            completion_thread.start()
        else:
            # For sync invocations, wait for completion before returning
            # Cleanup will happen in _wait_for_execution's finally block
            execution_details = self._wait_for_execution(execution_arn)
            if not self._is_cli_context():
                self._write_execution_result_to_stdout(execution_details, stdout)
            self._show_completion_commands(execution_arn, execution_details)

        return headers

    def _show_completion_commands(self, execution_arn: str, execution_details: dict):
        """
        Display execution summary table and next command suggestions after completion.
        Note: This only runs through sam local invoke, we don't show completion commands
              if the invoke request is happening through start-lambda or start-api.
        """
        if not self._is_cli_context():
            return

        summary_text = format_execution_details(execution_arn, execution_details)
        next_commands = format_next_commands_after_invoke(execution_arn)
        click.secho(f"{summary_text}\n{next_commands}", fg="yellow")

    def _write_execution_result_to_stdout(self, execution_details: dict, stdout):
        """Write the execution result to stdout for the HTTP service to read."""
        if not execution_details:
            return

        status = execution_details.get("Status")
        result = execution_details.get("Result")

        if status == "SUCCEEDED" and result:
            stdout.write_str(result)
            stdout.flush()

    def _wait_for_execution(self, execution_arn):
        """Poll the execution status until completion and return the final result."""

        callback_handler = DurableCallbackHandler(self.emulator_container.lambda_client)
        execution_details = None
        callback_thread = None
        stop_callback_prompts = threading.Event()

        try:
            while True:
                try:
                    LOG.debug("Polling execution status for ARN: %s", execution_arn)
                    execution_details = self.emulator_container.lambda_client.get_durable_execution(execution_arn)
                    status = execution_details.get("Status")

                    if status != "RUNNING":
                        stop_callback_prompts.set()  # Signal callback thread to stop
                        if callback_thread and callback_thread.is_alive():
                            callback_thread.join(timeout=0.5)  # Brief wait for thread cleanup
                        return execution_details

                    # Check for pending callbacks (only in CLI context)
                    if self._is_cli_context():
                        callback_id = callback_handler.check_for_pending_callbacks(execution_arn)
                        if callback_id:

                            def _prompt_in_thread():
                                if not stop_callback_prompts.is_set():
                                    # give the function logs time to settle after the invocation is suspended
                                    time.sleep(0.5)
                                    callback_sent = callback_handler.prompt_callback_response(
                                        execution_arn, callback_id, stop_callback_prompts
                                    )
                                    if callback_sent:
                                        click.echo("\n" + "─" * 80)

                            # Start callback prompt in separate thread so it doesn't block polling
                            callback_thread = threading.Thread(target=_prompt_in_thread, daemon=True)
                            callback_thread.start()

                    time.sleep(1)  # Poll every second
                except Exception as e:
                    LOG.error("Error polling execution status: %s", e)
                    break
        finally:
            stop_callback_prompts.set()  # Ensure callback thread knows to stop
            self._cleanup_if_needed()

        return execution_details

    def _cleanup_if_needed(self):
        """
        Clean up container if not in warm runtime mode.
        """
        if not self._is_warm_runtime:
            try:
                self._stop()
                self._delete()
            except Exception as e:
                LOG.error("Error stopping/deleting lambda container: %s", e)

    def stop(self):
        """Override to prevent cleanup during normal invoke flow."""
        # No-op during normal flow - cleanup happens in _cleanup_if_needed()
        pass

    def _stop(self):
        """Internal method to actually stop the container."""
        super().stop()

    def delete(self):
        """Override to prevent cleanup during normal invoke flow."""
        # No-op during normal flow - cleanup happens in _cleanup_if_needed()
        pass

    def _delete(self):
        """Internal method to actually delete the container."""
        super().delete()
