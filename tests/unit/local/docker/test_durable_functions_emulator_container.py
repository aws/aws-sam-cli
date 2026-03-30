"""
Unit tests for DurableFunctionsEmulatorContainer
"""

import os
import time
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch, mock_open
from parameterized import parameterized

import docker
import requests
from click import ClickException

from samcli.local.docker.durable_functions_emulator_container import DurableFunctionsEmulatorContainer
from samcli.local.docker.utils import to_posix_path


class TestDurableFunctionsEmulatorContainer(TestCase):
    def setUp(self):
        """Set up test fixtures"""
        self.mock_docker_client = Mock()
        self.mock_container = Mock()
        self.mock_docker_client.containers.create.return_value = self.mock_container

        self.env_patcher = patch.dict("os.environ", {}, clear=True)
        self.env_patcher.start()

    def tearDown(self):
        """Clean up after tests"""
        self.env_patcher.stop()

    def _create_container(self, existing_container=None):
        """Helper to create container with optional existing container"""
        return DurableFunctionsEmulatorContainer(
            container_client=self.mock_docker_client,
            existing_container=existing_container,
        )

    @parameterized.expand(
        [
            # (name, env_vars, expected_port, expected_container_name, is_external)
            ("managed_default", {}, 9014, "sam-durable-execution-emulator", False),
            (
                "managed_custom_port",
                {"DURABLE_EXECUTIONS_EMULATOR_PORT": "9999"},
                9999,
                "sam-durable-execution-emulator",
                False,
            ),
            ("managed_custom_name", {"DURABLE_EXECUTIONS_CONTAINER_NAME": "my-emulator"}, 9014, "my-emulator", False),
            ("external_mode", {"DURABLE_EXECUTIONS_EXTERNAL_EMULATOR_PORT": "8080"}, 8080, None, True),
            (
                "pin_image_tag",
                {"DURABLE_EXECUTIONS_EMULATOR_IMAGE_TAG": "v1.1.1"},
                9014,
                "sam-durable-execution-emulator",
                False,
            ),
        ]
    )
    def test_initialization(self, name, env_vars, expected_port, expected_name, is_external):
        """Test initialization determines mode, port, and container name"""
        with patch.dict("os.environ", env_vars, clear=True):
            container = self._create_container()
            self.assertEqual(container.port, expected_port)
            self.assertEqual(container._container_name, expected_name)
            self.assertEqual(container._is_external_emulator(), is_external)

    def test_initialization_with_invalid_external_port_raises_error(self):
        """Test that invalid external port raises RuntimeError"""
        with patch.dict("os.environ", {"DURABLE_EXECUTIONS_EXTERNAL_EMULATOR_PORT": "invalid"}, clear=True):
            with self.assertRaises(RuntimeError) as context:
                self._create_container()
            self.assertIn("Invalid port number", str(context.exception))

    def test_initialization_with_existing_container(self):
        """Test that existing container is preserved during initialization"""
        mock_existing = Mock()
        container = self._create_container(existing_container=mock_existing)
        self.assertEqual(container.container, mock_existing)

    @patch("samcli.local.docker.durable_functions_emulator_container.get_validated_container_client")
    def test_docker_client_lazy_loading(self, mock_get_validated_client):
        """Test that docker client is lazily loaded and cached"""
        mock_validated_client = Mock()
        mock_get_validated_client.return_value = mock_validated_client

        container = DurableFunctionsEmulatorContainer()
        mock_get_validated_client.assert_not_called()

        client = container._docker_client
        mock_get_validated_client.assert_called_once()
        self.assertEqual(client, mock_validated_client)

        # Subsequent access uses cached client
        client2 = container._docker_client
        mock_get_validated_client.assert_called_once()

    @parameterized.expand(
        [
            # (name, env_vars, should_create_container, should_start_container)
            ("managed_mode_creates_container", {}, True, True),
            ("external_mode_skips_container", {"DURABLE_EXECUTIONS_EXTERNAL_EMULATOR_PORT": "8080"}, False, False),
        ]
    )
    @patch("samcli.local.docker.durable_functions_emulator_container.is_image_current")
    def test_start_behavior_by_mode(self, name, env_vars, should_create, should_start, mock_is_current):
        """Test that start() behaves correctly for managed vs external mode"""
        mock_is_current.return_value = True

        with patch.dict("os.environ", env_vars, clear=True):
            container = self._create_container()
            container._wait_for_ready = Mock()
            container.start()

            if should_create:
                self.mock_docker_client.containers.create.assert_called_once()
                self.assertEqual(container.container, self.mock_container)
            else:
                self.mock_docker_client.containers.create.assert_not_called()
                self.assertIsNone(container.container)

            if should_start:
                self.mock_container.start.assert_called_once()
            else:
                self.mock_container.start.assert_not_called()

    @parameterized.expand(
        [
            ("stops_successfully", None, True),
            ("handles_stop_exception", Exception("Stop failed"), False),
        ]
    )
    def test_stop_behavior(self, name, stop_exception, should_remove):
        """Test that stop() handles success and failure cases"""
        container = self._create_container(existing_container=self.mock_container)
        if stop_exception:
            self.mock_container.stop.side_effect = stop_exception

        container.stop()

        self.mock_container.stop.assert_called_once()
        if should_remove:
            self.mock_container.remove.assert_called_once()
        else:
            self.mock_container.remove.assert_not_called()

    def test_stop_sets_container_to_none_after_successful_stop(self):
        """Test that stop() sets self.container to None in the finally block after success"""
        container = self._create_container(existing_container=self.mock_container)
        container._capture_emulator_logs = Mock()

        container.stop()

        self.assertIsNone(container.container)

    def test_stop_handles_not_found_and_sets_container_to_none(self):
        """Test that stop() handles docker.errors.NotFound when container is already removed"""
        container = self._create_container(existing_container=self.mock_container)
        container._capture_emulator_logs = Mock()
        self.mock_container.stop.side_effect = docker.errors.NotFound("Already removed")

        container.stop()

        self.mock_container.stop.assert_called_once()
        self.mock_container.remove.assert_not_called()
        self.assertIsNone(container.container)

    def test_stop_sets_container_to_none_after_generic_exception(self):
        """Test that stop() sets self.container to None in the finally block even after exception"""
        container = self._create_container(existing_container=self.mock_container)
        container._capture_emulator_logs = Mock()
        self.mock_container.stop.side_effect = Exception("Unexpected error")

        container.stop()

        self.assertIsNone(container.container)

    def test_stop_does_nothing_when_no_container(self):
        """Test that stop() does nothing when self.container is None"""
        container = self._create_container(existing_container=None)

        container.stop()

        self.mock_container.stop.assert_not_called()
        self.mock_container.remove.assert_not_called()
        self.assertIsNone(container.container)

    @parameterized.expand(
        [
            # (name, env_vars, container_exists, container_running, expected_reused, should_create_new)
            ("reuses_running_container", {}, True, True, True, False),
            ("creates_new_when_none_exists", {}, False, False, False, True),
            (
                "external_mode_always_reuses",
                {"DURABLE_EXECUTIONS_EXTERNAL_EMULATOR_PORT": "8080"},
                False,
                False,
                True,
                False,
            ),
        ]
    )
    @patch("samcli.local.docker.durable_functions_emulator_container.DurableFunctionsClient")
    def test_start_or_attach_behavior(
        self, name, env_vars, container_exists, container_running, expected_reused, should_create, mock_client_class
    ):
        """Test that start_or_attach() correctly handles reuse vs create scenarios"""
        with patch.dict("os.environ", env_vars, clear=True):
            container = self._create_container()

            if container_exists:
                mock_existing = Mock()
                mock_existing.status = "running" if container_running else "exited"
                self.mock_docker_client.containers.get.return_value = mock_existing
            else:
                self.mock_docker_client.containers.get.side_effect = Exception("Not found")

            container.start = Mock()
            result = container.start_or_attach()

            self.assertEqual(result, expected_reused)
            if should_create:
                container.start.assert_called_once()
            else:
                container.start.assert_not_called()

    @parameterized.expand(
        [
            ("running_container", "running", True),
            ("stopped_container", "exited", False),
            ("no_container", None, False),
        ]
    )
    def test_is_running_status(self, name, container_status, expected):
        """Test that is_running() correctly reports container status"""
        existing = self.mock_container if container_status else None
        if existing:
            self.mock_container.status = container_status

        container = self._create_container(existing_container=existing)
        result = container.is_running()

        self.assertEqual(result, expected)
        if existing:
            self.mock_container.reload.assert_called_once()

    def test_is_running_returns_false_when_reload_raises_exception(self):
        """Test that is_running() returns False when container.reload() raises an exception"""
        self.mock_container.reload.side_effect = Exception("Connection error")
        container = self._create_container(existing_container=self.mock_container)

        result = container.is_running()

        self.assertFalse(result)
        self.mock_container.reload.assert_called_once()

    @parameterized.expand(
        [
            ("with_container", True, "test logs"),
            ("without_container", False, "Durable Functions Emulator container not started"),
        ]
    )
    def test_get_logs(self, name, has_container, expected_logs):
        """Test that get_logs() returns logs or appropriate message"""
        existing = self.mock_container if has_container else None
        if existing:
            self.mock_container.logs.return_value = b"test logs"

        container = self._create_container(existing_container=existing)
        logs = container.get_logs(tail=100)

        self.assertEqual(logs, expected_logs)
        if existing:
            self.mock_container.logs.assert_called_once_with(tail=100)

    def test_get_logs_returns_error_message_when_logs_raises_exception(self):
        """Test that get_logs() returns error message when container.logs() raises an exception"""
        self.mock_container.logs.side_effect = Exception("Docker API error")
        container = self._create_container(existing_container=self.mock_container)

        result = container.get_logs()

        self.assertEqual(result, "Could not retrieve logs: Docker API error")

    @parameterized.expand(
        [
            ("x86_64", "aws-durable-execution-emulator-x86_64"),
            ("arm64", "aws-durable-execution-emulator-arm64"),
        ]
    )
    @patch("samcli.local.docker.durable_functions_emulator_container._get_host_architecture")
    def test_binary_selection_by_architecture(self, arch, expected_binary, mock_get_host_arch):
        """Test that correct emulator binary is selected for architecture"""
        mock_get_host_arch.return_value = arch
        container = self._create_container()
        self.assertEqual(container._get_emulator_binary_name(), expected_binary)

    @parameterized.expand(
        [
            # (name, env_vars, expected_port, expected_store, expected_scale)
            ("default_config", {}, 9014, "sqlite", "1"),
            ("custom_port", {"DURABLE_EXECUTIONS_EMULATOR_PORT": "9999"}, 9999, "sqlite", "1"),
            ("filesystem_store", {"DURABLE_EXECUTIONS_STORE_TYPE": "filesystem"}, 9014, "filesystem", "1"),
            ("custom_time_scale", {"DURABLE_EXECUTIONS_TIME_SCALE": "0.5"}, 9014, "sqlite", "0.5"),
            (
                "all_custom",
                {
                    "DURABLE_EXECUTIONS_EMULATOR_PORT": "8888",
                    "DURABLE_EXECUTIONS_STORE_TYPE": "filesystem",
                    "DURABLE_EXECUTIONS_TIME_SCALE": "2.0",
                },
                8888,
                "filesystem",
                "2.0",
            ),
        ]
    )
    @patch("samcli.local.docker.durable_functions_emulator_container.is_image_current")
    @patch("samcli.local.docker.durable_functions_emulator_container._get_host_architecture")
    @patch("os.makedirs")
    @patch("os.getcwd")
    @patch("pathlib.Path.exists")
    def test_create_container(
        self,
        name,
        env_vars,
        expected_port,
        expected_store,
        expected_scale,
        mock_path_exists,
        mock_getcwd,
        mock_makedirs,
        mock_get_host_arch,
        mock_is_current,
    ):
        """Test container creation with all configuration permutations"""
        mock_get_host_arch.return_value = "x86_64"
        test_dir = "/test/dir"
        mock_getcwd.return_value = test_dir
        mock_path_exists.return_value = True
        mock_is_current.return_value = True

        # Mock image already exists
        mock_image = Mock()
        self.mock_docker_client.images.get.return_value = mock_image

        with patch.dict("os.environ", env_vars, clear=True):
            container = self._create_container()
            container._RAPID_SOURCE_PATH = Path(__file__).parent
            container._wait_for_ready = Mock()
            container.start()

            # Verify container was created
            self.mock_docker_client.containers.create.assert_called_once()
            call_args = self.mock_docker_client.containers.create.call_args

            self.assertEqual(call_args.kwargs["working_dir"], "/tmp/.durable-executions-local")

            # Verify port configuration
            self.assertEqual(call_args.kwargs["ports"], {f"{expected_port}/tcp": expected_port})

            # Verify environment variables
            environment = call_args.kwargs["environment"]
            self.assertEqual(environment["DURABLE_EXECUTION_TIME_SCALE"], expected_scale)

            # Verify volumes
            volumes = call_args.kwargs["volumes"]
            expected_data_dir = os.path.join(test_dir, ".durable-executions-local")
            expected_volume_key = to_posix_path(expected_data_dir)
            self.assertIn(expected_volume_key, volumes)
            self.assertEqual(volumes[expected_volume_key]["bind"], "/tmp/.durable-executions-local")
            self.assertEqual(volumes[expected_volume_key]["mode"], "rw")

            # Verify networking
            self.assertEqual(call_args.kwargs["extra_hosts"], {"host.docker.internal": "host-gateway"})

            # Verify directory creation
            mock_makedirs.assert_called_once_with(expected_data_dir, exist_ok=True)

            # Verify container lifecycle
            self.assertEqual(container.container, self.mock_container)
            self.mock_container.start.assert_called_once()

    @parameterized.expand(
        [
            # (name, image_exists, is_current, should_pull)
            ("image_current", True, True, False),
            ("image_outdated", True, False, True),
            ("image_missing", False, None, True),
        ]
    )
    @patch("samcli.local.docker.durable_functions_emulator_container.is_image_current")
    def test_image_pull_behavior(self, name, image_exists, is_current, should_pull, mock_is_current):
        """Test that images are pulled only when necessary"""
        container = self._create_container()

        if image_exists:
            mock_image = Mock()
            self.mock_docker_client.images.get.return_value = mock_image
            mock_is_current.return_value = is_current
        else:
            self.mock_docker_client.images.get.side_effect = docker.errors.ImageNotFound("Not found")

        container._pull_image_if_needed()

        if should_pull:
            self.mock_docker_client.images.pull.assert_called_once()
        else:
            self.mock_docker_client.images.pull.assert_not_called()

    def test_image_pull_failure_raises_click_exception(self):
        """Test that image pull failures raise ClickException"""
        container = self._create_container()
        self.mock_docker_client.images.get.side_effect = docker.errors.ImageNotFound("Not found")
        self.mock_docker_client.images.pull.side_effect = Exception("Network error")

        with self.assertRaises(ClickException) as context:
            container._pull_image_if_needed()
        self.assertIn("Failed to pull emulator image", str(context.exception))

    @patch("samcli.local.docker.durable_functions_emulator_container.requests")
    def test_start_durable_execution_success(self, mock_requests):
        """Test that start_durable_execution() posts correct payload and returns response json"""
        mock_response = Mock()
        mock_response.json.return_value = {"executionId": "abc-123"}
        mock_requests.post.return_value = mock_response

        container = self._create_container()
        durable_config = {"ExecutionTimeout": 300, "RetentionPeriodInDays": 7}
        result = container.start_durable_execution("my-exec", '{"key": "val"}', "http://host:3001", durable_config)

        self.assertEqual(result, {"executionId": "abc-123"})
        mock_requests.post.assert_called_once()
        call_kwargs = mock_requests.post.call_args
        payload = call_kwargs.kwargs["json"]
        self.assertEqual(payload["ExecutionName"], "my-exec")
        self.assertEqual(payload["Input"], '{"key": "val"}')
        self.assertEqual(payload["LambdaEndpoint"], "http://host:3001")
        self.assertEqual(payload["ExecutionTimeoutSeconds"], 300)
        self.assertEqual(payload["ExecutionRetentionPeriodDays"], 7)
        mock_response.raise_for_status.assert_called_once()

    @patch("samcli.local.docker.durable_functions_emulator_container.requests")
    def test_start_durable_execution_raises_runtime_error_on_exception(self, mock_requests):
        """Test that start_durable_execution() raises RuntimeError when request fails"""
        mock_requests.post.side_effect = Exception("Connection refused")

        container = self._create_container()
        with self.assertRaises(RuntimeError) as ctx:
            container.start_durable_execution("exec", "{}", "http://host:3001", {})

        self.assertIn("Failed to start durable execution", str(ctx.exception))
        self.assertIn("Connection refused", str(ctx.exception))

    @patch("samcli.local.docker.durable_functions_emulator_container.requests")
    def test_start_durable_execution_includes_response_details_in_error(self, mock_requests):
        """Test that error message includes status and response text when available"""
        mock_resp = Mock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        exc = Exception("HTTP error")
        exc.response = mock_resp
        mock_requests.post.side_effect = exc

        container = self._create_container()
        with self.assertRaises(RuntimeError) as ctx:
            container.start_durable_execution("exec", "{}", "http://host:3001", {})

        error_msg = str(ctx.exception)
        self.assertIn("Status: 500", error_msg)
        self.assertIn("Internal Server Error", error_msg)

    @patch("samcli.local.docker.durable_functions_emulator_container.requests")
    def test_wait_for_ready_succeeds_when_healthy(self, mock_requests):
        """Test that _wait_for_ready() succeeds when health check passes"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_requests.get.return_value = mock_response

        container = self._create_container(existing_container=self.mock_container)
        self.mock_container.status = "running"

        container._wait_for_ready(timeout=1)
        mock_requests.get.assert_called()

    @patch("samcli.local.docker.durable_functions_emulator_container.time")
    @patch("samcli.local.docker.durable_functions_emulator_container.requests")
    def test_wait_for_ready_retries_on_request_exception_then_times_out(self, mock_requests, mock_time):
        """Test that RequestException is caught and retried until timeout"""
        mock_requests.exceptions.RequestException = requests.exceptions.RequestException
        mock_requests.get.side_effect = requests.exceptions.RequestException("Connection refused")
        mock_time.time.side_effect = [0, 0.1, 0.6, 1.1]
        mock_time.strftime = time.strftime

        container = self._create_container(existing_container=self.mock_container)
        self.mock_container.status = "running"
        self.mock_container.logs.return_value = b"some logs"

        with self.assertRaises(RuntimeError) as ctx:
            container._wait_for_ready(timeout=1)

        self.assertIn("failed to become ready", str(ctx.exception))
        self.assertTrue(mock_requests.get.call_count >= 2)
        mock_time.sleep.assert_called_with(0.5)

    @patch("samcli.local.docker.durable_functions_emulator_container.time")
    @patch("samcli.local.docker.durable_functions_emulator_container.requests")
    def test_wait_for_ready_breaks_on_non_request_exception(self, mock_requests, mock_time):
        """Test that non-RequestException breaks the loop immediately"""
        mock_requests.exceptions.RequestException = requests.exceptions.RequestException
        self.mock_container.status = "running"
        self.mock_container.reload.side_effect = RuntimeError("Docker daemon error")
        self.mock_container.logs.return_value = b"error logs"
        mock_time.time.side_effect = [0, 0.1]
        mock_time.strftime = time.strftime

        container = self._create_container(existing_container=self.mock_container)

        with self.assertRaises(RuntimeError) as ctx:
            container._wait_for_ready(timeout=30)

        self.assertIn("failed to become ready", str(ctx.exception))
        self.mock_container.reload.assert_called_once()

    @patch("samcli.local.docker.durable_functions_emulator_container.time")
    @patch("samcli.local.docker.durable_functions_emulator_container.requests")
    def test_wait_for_ready_raises_when_container_not_running(self, mock_requests, mock_time):
        """Test that RuntimeError is raised when container status is not running"""
        mock_requests.exceptions.RequestException = requests.exceptions.RequestException
        self.mock_container.status = "exited"
        self.mock_container.logs.return_value = b"crash logs"
        mock_time.time.side_effect = [0, 0.1]
        mock_time.strftime = time.strftime

        container = self._create_container(existing_container=self.mock_container)

        with self.assertRaises(RuntimeError) as ctx:
            container._wait_for_ready(timeout=30)

        self.assertIn("failed to become ready", str(ctx.exception))

    @patch("samcli.local.docker.durable_functions_emulator_container.time")
    @patch("samcli.local.docker.durable_functions_emulator_container.requests")
    def test_wait_for_ready_logs_container_exited_status(self, mock_requests, mock_time):
        """Test that the RuntimeError raised on line 390 includes the container exit status"""
        mock_requests.exceptions.RequestException = requests.exceptions.RequestException
        self.mock_container.status = "exited"
        self.mock_container.logs.return_value = b"logs"
        mock_time.time.side_effect = [0, 0.1]
        mock_time.strftime = time.strftime

        container = self._create_container(existing_container=self.mock_container)

        with (
            self.assertRaises(RuntimeError),
            self.assertLogs("samcli.local.docker.durable_functions_emulator_container", level="ERROR") as log,
        ):
            container._wait_for_ready(timeout=30)

        self.assertTrue(
            any("Durable Functions Emulator container exited with status: exited" in msg for msg in log.output)
        )

    @patch("samcli.local.docker.durable_functions_emulator_container.time")
    @patch("samcli.local.docker.durable_functions_emulator_container.requests")
    def test_wait_for_ready_handles_log_retrieval_failure(self, mock_requests, mock_time):
        """Test that failure to retrieve logs after timeout does not prevent RuntimeError"""
        mock_requests.exceptions.RequestException = requests.exceptions.RequestException
        mock_requests.get.side_effect = requests.exceptions.RequestException("refused")
        mock_time.time.side_effect = [0, 1.1]
        mock_time.strftime = time.strftime
        self.mock_container.status = "running"
        self.mock_container.logs.side_effect = Exception("Cannot get logs")

        container = self._create_container(existing_container=self.mock_container)

        with self.assertRaises(RuntimeError) as ctx:
            container._wait_for_ready(timeout=1)

        self.assertIn("failed to become ready", str(ctx.exception))

    @parameterized.expand(
        [
            # (name, env_value, has_container, should_capture, expected_logs)
            ("enabled_with_container", "1", True, True, "test logs"),
            ("enabled_true_with_container", "true", True, True, "test logs"),
            ("disabled_empty", "", False, False, None),
            ("disabled_none", None, False, False, None),
            ("enabled_no_container", "1", False, False, None),
        ]
    )
    @patch("builtins.open", new_callable=mock_open)
    @patch("os.getcwd")
    @patch("time.strftime")
    def test_log_capture(
        self, name, env_value, has_container, should_capture, expected_logs, mock_strftime, mock_getcwd, mock_file
    ):
        """Test log capture detection and behavior"""
        mock_strftime.return_value = "2025-11-29T12-00-00"
        mock_getcwd.return_value = "/test/dir"

        env = {"DURABLE_EXECUTIONS_CAPTURE_LOGS": env_value} if env_value is not None else {}
        with patch.dict("os.environ", env, clear=True):
            existing = self.mock_container if has_container else None
            container = self._create_container(existing_container=existing)

            if has_container:
                self.mock_container.logs.return_value = b"test logs"

            container._capture_emulator_logs()

            if should_capture:
                mock_file.assert_called_once()
                expected_path = os.path.join(
                    "/test/dir", ".durable-executions-local", "durable-execution-emulator-2025-11-29T12-00-00.log"
                )
                mock_file.assert_called_with(expected_path, "w")
            else:
                mock_file.assert_not_called()

    @patch("builtins.open", new_callable=mock_open)
    @patch("os.getcwd")
    def test_log_capture_handles_exceptions_gracefully(self, mock_getcwd, mock_file):
        """Test that log capture exceptions don't crash the application"""
        with patch.dict("os.environ", {"DURABLE_EXECUTIONS_CAPTURE_LOGS": "1"}, clear=True):
            mock_getcwd.return_value = "/test/dir"
            mock_file.side_effect = IOError("Write failed")

            container = self._create_container(existing_container=self.mock_container)
            self.mock_container.logs.return_value = b"test logs"

            container._capture_emulator_logs()  # Should not raise

    @patch("samcli.local.docker.durable_functions_emulator_container.DurableFunctionsClient")
    def test_start_or_attach_stops_and_removes_non_running_container(self, mock_client_class):
        """Test that start_or_attach stops/removes a non-running existing container and creates a new one"""
        container = self._create_container()

        mock_existing = Mock()
        mock_existing.status = "exited"
        self.mock_docker_client.containers.get.return_value = mock_existing

        container.start = Mock()
        result = container.start_or_attach()

        mock_existing.stop.assert_called_once()
        mock_existing.remove.assert_called_once()
        container.start.assert_called_once()
        self.assertFalse(result)

    @patch("samcli.local.docker.durable_functions_emulator_container.DurableFunctionsClient")
    def test_start_or_attach_handles_stop_remove_failure_gracefully(self, mock_client_class):
        """Test that start_or_attach handles exceptions when stopping/removing a non-running container"""
        container = self._create_container()

        mock_existing = Mock()
        mock_existing.status = "exited"
        mock_existing.stop.side_effect = Exception("Stop failed")
        self.mock_docker_client.containers.get.return_value = mock_existing

        container.start = Mock()
        result = container.start_or_attach()

        mock_existing.stop.assert_called_once()
        container.start.assert_called_once()
        self.assertFalse(result)

    def test_stop_skips_container_operations_in_external_mode(self):
        """Test that stop() returns early without stopping container in external emulator mode"""
        with patch.dict("os.environ", {"DURABLE_EXECUTIONS_EXTERNAL_EMULATOR_PORT": "8080"}, clear=True):
            container = self._create_container(existing_container=self.mock_container)
            container._capture_emulator_logs = Mock()

            container.stop()

            container._capture_emulator_logs.assert_not_called()
            self.mock_container.stop.assert_not_called()
            self.mock_container.remove.assert_not_called()

    def test_stop_captures_logs_before_stopping(self):
        """Test that stop() captures logs before stopping container"""
        with patch.dict("os.environ", {"DURABLE_EXECUTIONS_CAPTURE_LOGS": "1"}, clear=True):
            container = self._create_container(existing_container=self.mock_container)
            container._capture_emulator_logs = Mock()

            container.stop()

            container._capture_emulator_logs.assert_called_once()
            self.mock_container.stop.assert_called_once()
