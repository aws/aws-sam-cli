"""
Unit tests for DurableFunctionsEmulatorContainer
"""

import os
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch, mock_open
from parameterized import parameterized

import docker
from click import ClickException

from samcli.local.docker.durable_functions_emulator_container import DurableFunctionsEmulatorContainer


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
    ):
        """Test container creation with all configuration permutations"""
        mock_get_host_arch.return_value = "x86_64"
        test_dir = "/test/dir"
        mock_getcwd.return_value = test_dir
        mock_path_exists.return_value = True

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

            # Verify built image is used
            self.assertEqual(
                call_args.kwargs["image"], "samcli/durable-execution-emulator:aws-durable-execution-emulator-x86_64"
            )
            self.assertEqual(call_args.kwargs["working_dir"], "/tmp/.durable-executions-local")

            # Verify port configuration
            self.assertEqual(call_args.kwargs["ports"], {f"{expected_port}/tcp": expected_port})

            # Verify environment variables
            environment = call_args.kwargs["environment"]
            self.assertEqual(environment["EXECUTION_STORE_TYPE"], expected_store)
            self.assertEqual(environment["EXECUTION_TIME_SCALE"], expected_scale)
            self.assertEqual(environment["PORT"], str(expected_port))

            # Verify volumes
            volumes = call_args.kwargs["volumes"]
            expected_data_dir = os.path.join(test_dir, ".durable-executions-local")
            self.assertIn(expected_data_dir, volumes)
            self.assertEqual(volumes[expected_data_dir]["bind"], "/tmp/.durable-executions-local")
            self.assertEqual(volumes[expected_data_dir]["mode"], "rw")

            # Verify networking
            self.assertEqual(call_args.kwargs["extra_hosts"], {"host.docker.internal": "host-gateway"})

            # Verify directory creation
            mock_makedirs.assert_called_once_with(expected_data_dir, exist_ok=True)

            # Verify container lifecycle
            self.assertEqual(container.container, self.mock_container)
            self.mock_container.start.assert_called_once()

    def test_start_raises_error_when_binary_not_found(self):
        """Test that start() raises error when emulator binary is missing"""
        container = self._create_container()
        container._RAPID_SOURCE_PATH = Path("/nonexistent/path")
        with self.assertRaises(RuntimeError) as context:
            container.start()
        self.assertIn("Durable Functions Emulator binary not found", str(context.exception))

    @parameterized.expand(
        [
            (
                "x86_64",
                "aws-durable-execution-emulator-x86_64",
                "samcli/durable-execution-emulator:aws-durable-execution-emulator-x86_64",
            ),
            (
                "arm64",
                "aws-durable-execution-emulator-arm64",
                "samcli/durable-execution-emulator:aws-durable-execution-emulator-arm64",
            ),
        ]
    )
    @patch("samcli.local.docker.durable_functions_emulator_container._get_host_architecture")
    @patch("samcli.local.docker.durable_functions_emulator_container.create_tarball")
    @patch("samcli.local.docker.durable_functions_emulator_container.get_tar_filter_for_windows")
    @patch("builtins.open", new_callable=mock_open)
    @patch("os.unlink")
    @patch("pathlib.Path.exists")
    def test_build_emulator_image_creates_new_image(
        self,
        arch,
        binary_name,
        expected_tag,
        mock_path_exists,
        mock_unlink,
        mock_file,
        mock_tar_filter,
        mock_create_tarball,
        mock_get_host_arch,
    ):
        """Test building emulator image when it doesn't exist, including dockerfile generation and image tag"""
        mock_get_host_arch.return_value = arch
        mock_tar_filter.return_value = None
        mock_tarball = Mock()
        mock_create_tarball.return_value.__enter__.return_value = mock_tarball
        mock_path_exists.return_value = True

        # Mock image doesn't exist
        self.mock_docker_client.images.get.side_effect = docker.errors.ImageNotFound("not found")
        mock_build_result = Mock()
        self.mock_docker_client.images.build.return_value = mock_build_result

        container = self._create_container()
        container._RAPID_SOURCE_PATH = Path(__file__).parent

        result = container._build_emulator_image()

        # Verify image tag generation
        self.assertEqual(result, expected_tag)
        tag = container._get_emulator_image_tag(binary_name)
        self.assertEqual(tag, expected_tag)

        # Verify dockerfile generation
        dockerfile = container._generate_emulator_dockerfile(binary_name)
        self.assertIn(f"FROM {container._EMULATOR_IMAGE}", dockerfile)
        self.assertIn(f"COPY {binary_name} /usr/local/bin/{binary_name}", dockerfile)
        self.assertIn(f"RUN chmod +x /usr/local/bin/{binary_name}", dockerfile)

        # Verify image was built
        self.mock_docker_client.images.build.assert_called_once()
        build_call = self.mock_docker_client.images.build.call_args
        self.assertEqual(build_call.kwargs["tag"], expected_tag)
        self.assertTrue(build_call.kwargs["rm"])
        self.assertTrue(build_call.kwargs["custom_context"])

        # Verify tarball was created with correct filter
        mock_create_tarball.assert_called_once()

    @parameterized.expand(
        [
            ("x86_64", "samcli/durable-execution-emulator:aws-durable-execution-emulator-x86_64"),
            ("arm64", "samcli/durable-execution-emulator:aws-durable-execution-emulator-arm64"),
        ]
    )
    @patch("samcli.local.docker.durable_functions_emulator_container._get_host_architecture")
    @patch("pathlib.Path.exists")
    def test_build_emulator_image_reuses_existing(self, arch, expected_tag, mock_path_exists, mock_get_host_arch):
        """Test that existing image is reused without rebuilding"""
        mock_get_host_arch.return_value = arch
        mock_path_exists.return_value = True
        mock_image = Mock()
        self.mock_docker_client.images.get.return_value = mock_image

        container = self._create_container()
        container._RAPID_SOURCE_PATH = Path(__file__).parent

        result = container._build_emulator_image()

        # Verify image was not built
        self.mock_docker_client.images.build.assert_not_called()
        self.assertEqual(result, expected_tag)

    @parameterized.expand(
        [
            ("x86_64", "samcli/durable-execution-emulator:aws-durable-execution-emulator-x86_64"),
            ("arm64", "samcli/durable-execution-emulator:aws-durable-execution-emulator-arm64"),
        ]
    )
    @patch("samcli.local.docker.durable_functions_emulator_container._get_host_architecture")
    @patch("os.makedirs")
    @patch("os.getcwd")
    @patch("pathlib.Path.exists")
    def test_start_uses_built_image(
        self, arch, expected_tag, mock_path_exists, mock_getcwd, mock_makedirs, mock_get_host_arch
    ):
        """Test that start() uses the built image instead of base image"""
        mock_get_host_arch.return_value = arch
        mock_getcwd.return_value = "/test/dir"
        mock_path_exists.return_value = True

        # Mock image already exists
        mock_image = Mock()
        self.mock_docker_client.images.get.return_value = mock_image

        container = self._create_container()
        container._RAPID_SOURCE_PATH = Path(__file__).parent
        container._wait_for_ready = Mock()

        container.start()

        # Verify container was created with built image tag
        call_args = self.mock_docker_client.containers.create.call_args
        self.assertEqual(call_args.kwargs["image"], expected_tag)

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
    def test_wait_for_ready_succeeds_when_healthy(self, mock_requests):
        """Test that _wait_for_ready() succeeds when health check passes"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_requests.get.return_value = mock_response

        container = self._create_container(existing_container=self.mock_container)
        self.mock_container.status = "running"

        container._wait_for_ready(timeout=1)
        mock_requests.get.assert_called()

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

    def test_stop_captures_logs_before_stopping(self):
        """Test that stop() captures logs before stopping container"""
        with patch.dict("os.environ", {"DURABLE_EXECUTIONS_CAPTURE_LOGS": "1"}, clear=True):
            container = self._create_container(existing_container=self.mock_container)
            container._capture_emulator_logs = Mock()

            container.stop()

            container._capture_emulator_logs.assert_called_once()
            self.mock_container.stop.assert_called_once()
