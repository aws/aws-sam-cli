"""
Unit tests for DurableLambdaContainer
"""

from unittest import TestCase, mock
from unittest.mock import Mock, patch, MagicMock
from parameterized import parameterized

from samcli.lib.utils.packagetype import ZIP
from samcli.local.docker.durable_lambda_container import DurableLambdaContainer
from samcli.local.docker.lambda_container import LambdaContainer

CONTAINER_ID = "0123456789abcdef0123"
NETWORK_HOST = "sam-durable-function-0123456789ab"
NETWORK_ENDPOINT = f"http://{NETWORK_HOST}:8080"


class TestDurableLambdaContainer(TestCase):
    def setUp(self):
        """Set up common test fixtures"""
        self.mock_lambda_init_patch = patch("samcli.local.docker.durable_lambda_container.LambdaContainer.__init__")
        self.mock_lambda_init = self.mock_lambda_init_patch.start()

    def tearDown(self):
        """Clean up patches"""
        self.mock_lambda_init_patch.stop()

    def _create_container(self, mock_emulator=None, is_warm_runtime=False):
        """Helper to create DurableLambdaContainer with default parameters"""
        if mock_emulator is None:
            mock_emulator = Mock()
            mock_emulator.port = 5000

        container = DurableLambdaContainer(
            "python3.13",
            None,
            "handler",
            ZIP,
            None,
            "/code",
            [],
            None,
            "x86_64",
            emulator_container=mock_emulator,
            is_warm_runtime=is_warm_runtime,
            durable_config={"ExecutionTimeout": 900, "RetentionPeriodInDays": 7},
        )
        # LambdaContainer.__init__ is patched out, so set the state it and create() would.
        container.id = CONTAINER_ID
        container._network_id = None
        container._container_opts = None
        container._network_host = NETWORK_HOST
        return container

    @parameterized.expand(
        [
            ("containerized_emulator", False, "http://sam-durable-execution-emulator:5000"),
            ("external_emulator", True, "http://host.docker.internal:5000"),
        ]
    )
    def test_creates_lambda_container_with_emulator(self, name, is_external_emulator, expected_endpoint):
        """Test that DurableLambdaContainer properly initializes with emulator and environment"""
        mock_emulator = Mock()
        mock_emulator.port = 5000
        mock_emulator.network_endpoint = "http://sam-durable-execution-emulator:5000"
        mock_emulator._is_external_emulator = Mock(return_value=is_external_emulator)
        container = self._create_container(mock_emulator)

        # Verify it inherits from LambdaContainer
        self.assertIsInstance(container, LambdaContainer)

        # Verify emulator is set
        self.assertEqual(container.emulator_container, mock_emulator)
        self.assertFalse(container._is_warm_runtime)

        # Verify parent __init__ was called
        self.mock_lambda_init.assert_called_once()

        # Verify parent __init__ was called with updated kwargs
        call_kwargs = self.mock_lambda_init.call_args[1]

        # Verify AWS_ENDPOINT_URL_LAMBDA points at the emulator
        self.assertIn("env_vars", call_kwargs)
        self.assertEqual(call_kwargs["env_vars"]["AWS_ENDPOINT_URL_LAMBDA"], expected_endpoint)

        # Verify extra_hosts is set
        self.assertIn("extra_hosts", call_kwargs)
        self.assertEqual(call_kwargs["extra_hosts"]["host.docker.internal"], "host-gateway")

    def test_respects_container_host_interface(self):
        """The host interface the RIE port is published on is left to the caller"""
        mock_emulator = Mock()
        mock_emulator.port = 5000
        mock_emulator._is_external_emulator = Mock(return_value=False)
        DurableLambdaContainer(
            "python3.13",
            None,
            "handler",
            ZIP,
            None,
            "/code",
            [],
            None,
            "x86_64",
            emulator_container=mock_emulator,
            durable_config={},
            container_host_interface="127.0.0.1",
        )

        self.assertEqual(self.mock_lambda_init.call_args[1]["container_host_interface"], "127.0.0.1")

    @patch("samcli.local.docker.durable_lambda_container.uuid.uuid4")
    @patch("samcli.local.docker.durable_lambda_container.LambdaContainer.create")
    def test_create_joins_emulator_network(self, mock_parent_create, mock_uuid4):
        mock_parent_create.return_value = CONTAINER_ID
        mock_uuid4.return_value.hex = "abcdef0123456789abcdef0123456789"
        mock_emulator = Mock()
        mock_emulator._is_external_emulator = Mock(return_value=False)
        mock_emulator.get_or_create_network.return_value.name = "sam-durable-execution"
        container = self._create_container(mock_emulator)
        container._container_opts = {"privileged": True}

        self.assertEqual(container.create(Mock()), CONTAINER_ID)

        # Joined at creation time under a name, not attached afterwards with an alias
        mock_emulator.get_or_create_network.return_value.connect.assert_not_called()
        self.assertEqual(
            container._container_opts,
            {
                "privileged": True,
                "name": "sam-durable-function-abcdef012345",
                "hostname": "sam-durable-function-abcdef012345",
                "network": "sam-durable-execution",
            },
        )
        self.assertEqual(container._get_lambda_container_endpoint(), "http://sam-durable-function-abcdef012345:8080")

    @patch("samcli.local.docker.durable_lambda_container.LambdaContainer.create")
    def test_create_uses_new_name_each_time(self, mock_parent_create):
        mock_emulator = Mock()
        mock_emulator._is_external_emulator = Mock(return_value=False)
        container = self._create_container(mock_emulator)

        container.create(Mock())
        first_name = container._container_opts["name"]
        container.create(Mock())

        self.assertNotEqual(container._container_opts["name"], first_name)

    @patch("samcli.local.docker.durable_lambda_container.LambdaContainer.create")
    def test_create_skips_emulator_network_for_external_emulator(self, mock_parent_create):
        mock_emulator = Mock()
        mock_emulator._is_external_emulator = Mock(return_value=True)
        container = self._create_container(mock_emulator)

        container.create(Mock())

        mock_emulator.get_or_create_network.assert_not_called()
        self.assertIsNone(container._container_opts)

    @patch("samcli.local.docker.durable_lambda_container.LambdaContainer.create")
    def test_create_on_host_network_reaches_emulator_through_localhost(self, mock_parent_create):
        mock_emulator = Mock()
        mock_emulator.port = 5000
        mock_emulator._is_external_emulator = Mock(return_value=False)
        container = self._create_container(mock_emulator)
        container._network_id = "host"
        container._env_vars = {}
        container.get_port = Mock(return_value=8080)

        container.create(Mock())

        mock_emulator.get_or_create_network.assert_not_called()
        self.assertEqual(container._env_vars["AWS_ENDPOINT_URL_LAMBDA"], "http://localhost:5000")
        self.assertEqual(container._get_lambda_container_endpoint(), "http://host.docker.internal:8080")

    @parameterized.expand(
        [
            (False, NETWORK_ENDPOINT, False),  # is_external_emulator=False, CLI context
            (True, "http://localhost:8080", False),  # is_external_emulator=True, CLI context
            (False, NETWORK_ENDPOINT, True),  # is_external_emulator=False, HTTP context
        ]
    )
    @patch("samcli.local.docker.durable_lambda_container.DurableCallbackHandler")
    @patch("samcli.local.docker.durable_lambda_container.click.secho")
    @patch("samcli.local.docker.durable_lambda_container.format_execution_started")
    @patch("samcli.local.docker.durable_lambda_container.format_next_commands_after_invoke")
    @patch("samcli.local.docker.durable_lambda_container.format_execution_details")
    @patch("samcli.local.docker.durable_lambda_container.has_request_context")
    @patch("samcli.local.docker.durable_lambda_container.LambdaContainer.start")
    def test_sync_wait_for_result(
        self,
        is_external_emulator,
        expected_emulator_endpoint,
        has_flask_request_context,
        mock_start,
        mock_has_request_context,
        mock_format_execution_details,
        mock_format_next_commands,
        mock_format_execution_started,
        mock_secho,
        mock_callback_handler_class,
    ):
        """Test wait_for_result for sync invocation waits for completion and shows commands based on context"""
        mock_has_request_context.return_value = has_flask_request_context
        mock_format_execution_details.return_value = "Execution details"
        mock_format_next_commands.return_value = "Next commands"
        mock_format_execution_started.return_value = "Execution started"

        # Mock callback handler to return no pending callbacks
        mock_callback_handler = Mock()
        mock_callback_handler.check_for_pending_callbacks.return_value = None
        mock_callback_handler_class.return_value = mock_callback_handler

        mock_emulator = Mock()
        mock_emulator.start_or_attach = Mock()
        mock_emulator._is_external_emulator = Mock(return_value=is_external_emulator)

        mock_customer_provided_event = {"test": "event"}
        mock_customer_provided_execution_name = "mock-durable-execution-name"
        mock_execution_arn = "mock-durable-execution-arn"

        mock_emulator.start_durable_execution = Mock(return_value={"ExecutionArn": mock_execution_arn})

        # Simulate polling: first two calls return RUNNING, third returns SUCCEEDED
        mock_get_durable_execution_succeeded_response = {"Status": "SUCCEEDED", "Result": '{"message": "success"}'}
        mock_emulator.lambda_client.get_durable_execution = Mock(
            side_effect=[
                {"Status": "RUNNING"},
                {"Status": "RUNNING"},
                mock_get_durable_execution_succeeded_response,
            ]
        )

        container = self._create_container(mock_emulator)

        container.start_logs_thread_if_not_alive = Mock()
        container.get_port = Mock(return_value=8080)
        container._wait_for_socket_connection = Mock()

        mock_stdout = Mock()
        mock_stderr = Mock()

        # Call the method (sync invocation)
        headers = container.wait_for_result(
            full_path="test-function",
            event=mock_customer_provided_event,
            stdout=mock_stdout,
            stderr=mock_stderr,
            durable_execution_name=mock_customer_provided_execution_name,
        )

        # Verify lambda container methods were called
        container.start_logs_thread_if_not_alive.assert_called_once()
        container._wait_for_socket_connection.assert_called_once()

        # Verify emulator was used to start the execution
        mock_emulator.start_durable_execution.assert_called_once_with(
            mock_customer_provided_execution_name,
            mock_customer_provided_event,
            expected_emulator_endpoint,
            {"ExecutionTimeout": 900, "RetentionPeriodInDays": 7},
        )

        # Verify callback handler was created
        mock_callback_handler_class.assert_called_once_with(mock_emulator.lambda_client)

        # Verify execution was polled multiple times until completion
        self.assertEqual(mock_emulator.lambda_client.get_durable_execution.call_count, 3)
        mock_emulator.lambda_client.get_durable_execution.assert_called_with(mock_execution_arn)

        # Verify stdout writing behavior based on context
        if has_flask_request_context:
            # HTTP context - should write to stdout
            mock_stdout.write_str.assert_called_once_with('{"message": "success"}')
            mock_stdout.flush.assert_called_once()
            # Should neither announce the execution nor show completion commands
            mock_format_execution_started.assert_not_called()
            mock_format_execution_details.assert_not_called()
            mock_format_next_commands.assert_not_called()
            mock_secho.assert_not_called()
        else:
            # CLI context - should not write to stdout
            mock_stdout.write_str.assert_not_called()
            mock_stdout.flush.assert_not_called()
            # Should announce the execution ARN as soon as the execution starts
            mock_format_execution_started.assert_called_once_with(mock_execution_arn)
            # Should show completion commands
            mock_format_execution_details.assert_called_once_with(
                mock_execution_arn, mock_get_durable_execution_succeeded_response
            )
            mock_format_next_commands.assert_called_once_with(mock_execution_arn)
            self.assertEqual(
                mock_secho.call_args_list,
                [
                    mock.call("Execution started", fg="yellow", err=True),
                    mock.call("Execution details\nNext commands", fg="yellow"),
                ],
            )

        # Verify headers are returned
        self.assertEqual(headers["X-Amz-Durable-Execution-Arn"], mock_execution_arn)

    @parameterized.expand(
        [
            (False,),  # has_request_context=False (CLI context) - user is prompted to respond to callbacks
            (True,),  # has_request_context=True (HTTP context) - user is not prompted
        ]
    )
    @patch("samcli.local.docker.durable_lambda_container.has_request_context")
    @patch("samcli.local.docker.durable_lambda_container.threading.Thread")
    @patch("samcli.local.docker.durable_lambda_container.DurableCallbackHandler")
    @patch("samcli.local.docker.durable_lambda_container.LambdaContainer.start")
    def test_sync_wait_for_result_with_callbacks(
        self, has_request_context, mock_start, mock_callback_handler_class, mock_thread_class, mock_has_request_context
    ):
        """Test callback thread lifecycle: detection, prompt, and cleanup on completion"""
        mock_has_request_context.return_value = has_request_context
        is_cli_context = not has_request_context
        mock_execution_arn = "arn:123"

        mock_emulator = Mock()
        mock_emulator._is_external_emulator = Mock(return_value=False)
        mock_emulator.start_durable_execution = Mock(return_value={"ExecutionArn": mock_execution_arn})
        # Execution runs for 3 polls, callback detected on 3rd, then completes
        mock_emulator.lambda_client.get_durable_execution = Mock(
            side_effect=[
                {"Status": "RUNNING"},
                {"Status": "RUNNING"},
                {"Status": "RUNNING"},
                {"Status": "SUCCEEDED", "Output": "result"},
            ]
        )

        # Mock callback handler - no callback for first 2 polls, then callback detected
        mock_callback_handler = Mock()
        mock_callback_handler.check_for_pending_callbacks.side_effect = [None, None, "callback-123"]
        mock_callback_handler.prompt_callback_response.return_value = True
        mock_callback_handler_class.return_value = mock_callback_handler

        # Mock callback thread - capture target and execute it to verify prompt is called
        mock_callback_thread = Mock()
        mock_callback_thread.is_alive.return_value = True  # So join() gets called at cleanup

        def capture_and_execute_thread(target, **kwargs):
            target()  # Execute the thread function immediately
            return mock_callback_thread

        mock_thread_class.side_effect = capture_and_execute_thread

        container = self._create_container(mock_emulator)
        container.start_logs_thread_if_not_alive = Mock()
        container.get_port = Mock(return_value=8080)
        container._wait_for_socket_connection = Mock()

        container.wait_for_result(
            full_path="test-function",
            event={"test": "event"},
            stdout=Mock(),
            stderr=Mock(),
            durable_execution_name="test-execution",
        )

        if is_cli_context:
            # CLI context - validate the user was prompted to respond to the callback
            self.assertEqual(mock_callback_handler.check_for_pending_callbacks.call_count, 3)
            mock_callback_handler.check_for_pending_callbacks.assert_called_with(mock_execution_arn)

            # Verify callback prompt was called with correct arguments
            mock_callback_handler.prompt_callback_response.assert_called_once_with(
                mock_execution_arn, "callback-123", mock.ANY
            )

            # Verify callback thread was created with daemon=True and started
            mock_thread_class.assert_called_once_with(target=mock.ANY, daemon=True)
            mock_callback_thread.start.assert_called_once()

            # Verify thread cleanup: join called when execution completes
            mock_callback_thread.join.assert_called_once_with(timeout=0.5)
        else:
            # HTTP context - the user should not have been prompted
            mock_callback_handler.check_for_pending_callbacks.assert_not_called()
            mock_callback_handler.prompt_callback_response.assert_not_called()
            mock_thread_class.assert_not_called()

    @patch("samcli.local.docker.durable_lambda_container.DurableCallbackHandler")
    @patch("samcli.local.docker.durable_lambda_container.click.secho")
    @patch("samcli.local.docker.durable_lambda_container.has_request_context")
    @patch("samcli.local.docker.durable_lambda_container.LambdaContainer.start")
    def test_execution_arn_is_shown_before_polling_starts(
        self, mock_start, mock_has_request_context, mock_secho, mock_callback_handler_class
    ):
        """Test the execution ARN is shown before waiting on the execution, not only once it completes"""
        mock_has_request_context.return_value = False  # CLI context

        mock_callback_handler = Mock()
        mock_callback_handler.check_for_pending_callbacks.return_value = None
        mock_callback_handler_class.return_value = mock_callback_handler

        mock_execution_arn = "mock-durable-execution-arn"
        mock_emulator = Mock()
        mock_emulator._is_external_emulator = Mock(return_value=False)
        mock_emulator.start_durable_execution = Mock(return_value={"ExecutionArn": mock_execution_arn})

        secho_calls_when_first_polled = []

        def _record_and_complete(_arn):
            secho_calls_when_first_polled.append(mock_secho.call_count)
            return {"Status": "SUCCEEDED", "Result": "{}"}

        mock_emulator.lambda_client.get_durable_execution = Mock(side_effect=_record_and_complete)

        container = self._create_container(mock_emulator)
        container.start_logs_thread_if_not_alive = Mock()
        container.get_port = Mock(return_value=8080)
        container._wait_for_socket_connection = Mock()

        container.wait_for_result(
            full_path="test-function",
            event={"test": "event"},
            stdout=Mock(),
            stderr=Mock(),
            durable_execution_name="mock-durable-execution-name",
        )

        # The ARN was already printed by the time the execution was first polled
        self.assertGreaterEqual(secho_calls_when_first_polled[0], 1)
        self.assertIn(mock_execution_arn, mock_secho.call_args_list[0][0][0])

    @parameterized.expand(
        [
            (False, "mock-durable-execution-arn", True),  # CLI context with an ARN - announce it
            (True, "mock-durable-execution-arn", False),  # HTTP context - the caller gets the ARN in a header
            (False, None, False),  # no ARN returned by the emulator - nothing to announce
        ]
    )
    @patch("samcli.local.docker.durable_lambda_container.click.secho")
    @patch("samcli.local.docker.durable_lambda_container.format_execution_started")
    @patch("samcli.local.docker.durable_lambda_container.has_request_context")
    def test_show_execution_started(
        self,
        has_flask_request_context,
        execution_arn,
        should_announce,
        mock_has_request_context,
        mock_format_execution_started,
        mock_secho,
    ):
        """Test _show_execution_started only prints in CLI context and only when there is an ARN"""
        mock_has_request_context.return_value = has_flask_request_context
        mock_format_execution_started.return_value = "Execution started"

        container = self._create_container()
        container._show_execution_started(execution_arn)

        if should_announce:
            mock_format_execution_started.assert_called_once_with(execution_arn)
            mock_secho.assert_called_once_with("Execution started", fg="yellow", err=True)
        else:
            mock_format_execution_started.assert_not_called()
            mock_secho.assert_not_called()

    @parameterized.expand(
        [
            (False, NETWORK_ENDPOINT),  # internal emulator
            (True, "http://localhost:8080"),  # external emulator
        ]
    )
    # secho is patched to keep the started banner out of the test output. This test runs outside a
    # flask request context, so it counts as CLI context and the banner is printed, even though a
    # real Event invocation only ever arrives through start-lambda, where it is gated off.
    @patch("samcli.local.docker.durable_lambda_container.click.secho")
    @patch("samcli.local.docker.durable_lambda_container.DurableCallbackHandler")
    @patch("samcli.local.docker.durable_lambda_container.LambdaContainer.start")
    @patch("samcli.local.docker.durable_lambda_container.threading.Thread")
    def test_async_wait_for_result(
        self,
        is_external_emulator,
        expected_emulator_endpoint,
        mock_thread,
        mock_start,
        mock_callback_handler_class,
        mock_secho,
    ):
        """Test wait_for_result with async invocation returns immediately and polls in background"""
        # Mock callback handler to return no pending callbacks
        mock_callback_handler = Mock()
        mock_callback_handler.check_for_pending_callbacks.return_value = None
        mock_callback_handler_class.return_value = mock_callback_handler

        mock_emulator = Mock()
        mock_emulator.start_or_attach = Mock()
        mock_emulator._is_external_emulator = Mock(return_value=is_external_emulator)

        mock_customer_provided_event = {"test": "event"}
        mock_customer_provided_execution_name = "mock-durable-execution-name"
        mock_execution_arn = "mock-durable-execution-arn"

        mock_emulator.start_durable_execution = Mock(return_value={"ExecutionArn": mock_execution_arn})

        # Simulate polling in background thread: first two calls return RUNNING, third returns SUCCEEDED
        mock_get_durable_execution_succeeded_response = {"Status": "SUCCEEDED", "Output": "result"}
        mock_emulator.lambda_client.get_durable_execution = Mock(
            side_effect=[
                {"Status": "RUNNING"},
                {"Status": "RUNNING"},
                mock_get_durable_execution_succeeded_response,
            ]
        )

        mock_thread_instance = Mock()
        mock_thread.return_value = mock_thread_instance

        container = self._create_container(mock_emulator)

        container.start_logs_thread_if_not_alive = Mock()
        container.get_port = Mock(return_value=8080)
        container._wait_for_socket_connection = Mock()

        # Call the method with async invocation
        headers = container.wait_for_result(
            full_path="test-function",
            event=mock_customer_provided_event,
            stdout=Mock(),
            stderr=Mock(),
            durable_execution_name=mock_customer_provided_execution_name,
            invocation_type="Event",
        )

        # Verify lambda container methods were called
        container.start_logs_thread_if_not_alive.assert_called_once()
        container._wait_for_socket_connection.assert_called_once()

        # Verify emulator was used to start the execution
        mock_emulator.start_durable_execution.assert_called_once_with(
            mock_customer_provided_execution_name,
            mock_customer_provided_event,
            expected_emulator_endpoint,
            {"ExecutionTimeout": 900, "RetentionPeriodInDays": 7},
        )

        # Verify thread was created with daemon=True and started
        mock_thread.assert_called_once()
        call_kwargs = mock_thread.call_args[1]
        self.assertTrue(call_kwargs.get("daemon"))
        mock_thread_instance.start.assert_called_once()

        # Verify headers are returned immediately (before polling completes)
        self.assertEqual(headers["X-Amz-Durable-Execution-Arn"], mock_execution_arn)

        # Verify the background thread function polls for completion
        thread_target = mock_thread.call_args[1]["target"]
        thread_target()  # Execute the background function

        # Verify execution was polled multiple times in background until completion
        self.assertEqual(mock_emulator.lambda_client.get_durable_execution.call_count, 3)
        mock_emulator.lambda_client.get_durable_execution.assert_called_with(mock_execution_arn)

    @parameterized.expand(
        [
            ("not_warm", False, True),
            ("warm", True, False),
        ]
    )
    @patch("samcli.local.docker.durable_lambda_container.LambdaContainer.stop")
    @patch("samcli.local.docker.durable_lambda_container.LambdaContainer.delete")
    def test_cleanup_if_needed(self, name, is_warm_runtime, should_cleanup, mock_delete, mock_stop):
        """Test _cleanup_if_needed behavior based on warm runtime mode"""
        container = self._create_container(is_warm_runtime=is_warm_runtime)

        container._cleanup_if_needed()

        if should_cleanup:
            mock_stop.assert_called_once()
            mock_delete.assert_called_once()
        else:
            mock_stop.assert_not_called()
            mock_delete.assert_not_called()

    @patch("samcli.local.docker.durable_lambda_container.LambdaContainer.stop")
    def test_cleanup_if_needed_handles_exception(self, mock_stop):
        """Test _cleanup_if_needed handles exceptions gracefully"""
        mock_stop.side_effect = Exception("Stop failed")

        container = self._create_container()

        # Should not raise exception
        container._cleanup_if_needed()

    @patch("samcli.local.docker.durable_lambda_container.LambdaContainer.stop")
    @patch("samcli.local.docker.durable_lambda_container.LambdaContainer.delete")
    def test_lifecycle_methods_are_overridden(self, mock_parent_delete, mock_parent_stop):
        """Test stop() and delete() are overridden as no-ops, while _stop() and _delete() call parent"""
        container = self._create_container()

        # Inherited methods should be no-ops
        container.stop()
        container.delete()
        mock_parent_stop.assert_not_called()
        mock_parent_delete.assert_not_called()

        # Internal methods should call parent
        container._stop()
        container._delete()
        mock_parent_stop.assert_called_once()
        mock_parent_delete.assert_called_once()

    @parameterized.expand(
        [
            ("success", {"Status": "SUCCEEDED", "Result": '{"message": "success"}'}, True),
            ("failed", {"Status": "FAILED", "Error": {"Type": "Error", "Message": "Something went wrong"}}, False),
            ("no_result", {"Status": "SUCCEEDED"}, False),
            ("none_details", None, False),
        ]
    )
    def test_write_execution_result_to_stdout(self, name, execution_details, should_write):
        """Test _write_execution_result_to_stdout writes only on SUCCEEDED with Result"""
        container = self._create_container()
        mock_stdout = Mock()

        container._write_execution_result_to_stdout(execution_details, mock_stdout)

        if should_write:
            mock_stdout.write_str.assert_called_once_with(execution_details["Result"])
            mock_stdout.flush.assert_called_once()
        else:
            mock_stdout.write_str.assert_not_called()
            mock_stdout.flush.assert_not_called()
