"""
Unit tests for Container Client Factory

This module tests the ContainerClientFactory for creating appropriate container clients
based on administrator preferences and availability detection.
"""

import os
from unittest import TestCase
from unittest.mock import Mock, patch, call, mock_open
from parameterized import parameterized

from samcli.cli.context import Context
from samcli.local.docker.container_client_factory import ContainerClientFactory
from samcli.local.docker.container_engine import ContainerEngine
from samcli.local.docker.exceptions import (
    ContainerEnforcementException,
    ContainerNotReachableException,
)


class TestContainerClientFactory(TestCase):
    """Test the ContainerClientFactory"""

    def setUp(self):
        """Set up test fixtures"""
        # Reset environment variables
        self.original_docker_host = os.environ.get("DOCKER_HOST")
        if "DOCKER_HOST" in os.environ:
            del os.environ["DOCKER_HOST"]

    def tearDown(self):
        """Clean up test fixtures"""
        # Restore original environment
        if self.original_docker_host:
            os.environ["DOCKER_HOST"] = self.original_docker_host
        elif "DOCKER_HOST" in os.environ:
            del os.environ["DOCKER_HOST"]

    @patch("samcli.local.docker.container_client_factory.ContainerClientFactory.get_admin_container_preference")
    @patch("samcli.local.docker.container_client_factory.ContainerClientFactory._create_auto_detected_client")
    def test_create_client_no_preference(self, mock_auto_detect, mock_get_preference):
        """Test client creation with no admin preference"""
        mock_get_preference.return_value = None
        mock_client = Mock()
        mock_auto_detect.return_value = mock_client

        result = ContainerClientFactory.create_client()

        self.assertEqual(result, mock_client)
        mock_auto_detect.assert_called_once()

    @patch("samcli.local.docker.container_client_factory.ContainerClientFactory.get_admin_container_preference")
    @patch("samcli.local.docker.container_client_factory.ContainerClientFactory._create_enforced_client")
    def test_create_client_with_preference(self, mock_enforced, mock_get_preference):
        """Test client creation with admin preference"""
        mock_get_preference.return_value = "docker"
        mock_client = Mock()
        mock_enforced.return_value = mock_client

        result = ContainerClientFactory.create_client()

        self.assertEqual(result, mock_client)
        mock_enforced.assert_called_once_with("docker")

    @patch("samcli.local.docker.container_client_factory.ContainerClientFactory._try_create_docker_client")
    @patch("samcli.local.docker.container_client_factory.LOG")
    def test_create_enforced_client_docker_success(self, mock_log, mock_try_docker):
        """Test enforced Docker client creation success"""
        mock_client = Mock()
        mock_client.is_available.return_value = True
        mock_try_docker.return_value = mock_client

        result = ContainerClientFactory._create_enforced_client(ContainerEngine.DOCKER.value)

        self.assertEqual(result, mock_client)
        mock_log.debug.assert_called_with("Using Docker as Container Engine (enforced).")

    @patch("samcli.local.docker.container_client_factory.ContainerClientFactory._try_create_docker_client")
    @patch("samcli.local.docker.container_client_factory.ContainerClientFactory._get_error_message")
    def test_create_enforced_client_docker_unavailable(self, mock_error_msg, mock_try_docker):
        """Test enforced Docker client creation when Docker unavailable"""
        mock_client = Mock()
        mock_client.is_available.return_value = False
        mock_try_docker.return_value = mock_client
        mock_error_msg.return_value = "Docker not available"

        with self.assertRaises(ContainerEnforcementException):
            ContainerClientFactory._create_enforced_client(ContainerEngine.DOCKER.value)

    @patch("samcli.local.docker.container_client_factory.ContainerClientFactory._try_create_finch_client")
    @patch("samcli.local.docker.container_client_factory.LOG")
    def test_create_enforced_client_finch_success(self, mock_log, mock_try_finch):
        """Test enforced Finch client creation success"""
        mock_client = Mock()
        mock_client.is_available.return_value = True
        mock_try_finch.return_value = mock_client

        result = ContainerClientFactory._create_enforced_client(ContainerEngine.FINCH.value)

        self.assertEqual(result, mock_client)
        mock_log.debug.assert_called_with("Using Finch as Container Engine (enforced).")

    @patch("samcli.local.docker.container_client_factory.ContainerClientFactory._create_auto_detected_client")
    def test_create_enforced_client_unknown_preference(self, mock_auto_detect):
        """Test enforced client creation with unknown preference falls back to auto-detection"""
        mock_client = Mock()
        mock_auto_detect.return_value = mock_client

        result = ContainerClientFactory._create_enforced_client("unknown")

        self.assertEqual(result, mock_client)
        mock_auto_detect.assert_called_once()

    @patch("samcli.local.docker.container_client_factory.ContainerClientFactory._try_create_docker_client")
    @patch("samcli.local.docker.container_client_factory.LOG")
    def test_create_auto_detected_client_docker_success(self, mock_log, mock_try_docker):
        """Test auto-detection with Docker available"""
        mock_client = Mock()
        mock_client.is_available.return_value = True
        mock_try_docker.return_value = mock_client

        result = ContainerClientFactory._create_auto_detected_client()

        self.assertEqual(result, mock_client)
        mock_log.debug.assert_called_with("Using Docker as Container Engine.")

    @patch("samcli.local.docker.container_client_factory.ContainerClientFactory._try_create_docker_client")
    @patch("samcli.local.docker.container_client_factory.ContainerClientFactory._try_create_finch_client")
    @patch("samcli.local.docker.container_client_factory.LOG")
    def test_create_auto_detected_client_finch_fallback(self, mock_log, mock_try_finch, mock_try_docker):
        """Test auto-detection with Docker unavailable, Finch available"""
        # Docker unavailable
        docker_client = Mock()
        docker_client.is_available.return_value = False
        mock_try_docker.return_value = docker_client

        # Finch available
        finch_client = Mock()
        finch_client.is_available.return_value = True
        mock_try_finch.return_value = finch_client

        result = ContainerClientFactory._create_auto_detected_client()

        self.assertEqual(result, finch_client)
        mock_log.debug.assert_called_with("Using Finch as Container Engine.")

    @patch("samcli.local.docker.container_client_factory.ContainerClientFactory._try_create_docker_client")
    @patch("samcli.local.docker.container_client_factory.ContainerClientFactory._try_create_finch_client")
    @patch("samcli.local.docker.container_client_factory.ContainerClientFactory._get_error_message")
    def test_create_auto_detected_client_none_available(self, mock_error_msg, mock_try_finch, mock_try_docker):
        """Test auto-detection when no container runtime is available"""
        # Both unavailable
        mock_try_docker.return_value = None
        mock_try_finch.return_value = None
        mock_error_msg.return_value = "No container runtime available"

        with self.assertRaises(ContainerNotReachableException):
            ContainerClientFactory._create_auto_detected_client()

    @patch("samcli.local.docker.container_client_factory.DockerContainerClient")
    def test_try_create_docker_client_success(self, mock_docker_class):
        """Test successful Docker client creation"""
        mock_client = Mock()
        mock_docker_class.return_value = mock_client

        result = ContainerClientFactory._try_create_docker_client()

        self.assertEqual(result, mock_client)
        mock_docker_class.assert_called_once()

    @patch("samcli.local.docker.container_client_factory.DockerContainerClient")
    @patch("samcli.local.docker.container_client_factory.LOG")
    def test_try_create_docker_client_exception(self, mock_log, mock_docker_class):
        """Test Docker client creation with exception"""
        mock_docker_class.side_effect = Exception("Connection failed")

        result = ContainerClientFactory._try_create_docker_client()

        self.assertIsNone(result)
        mock_log.debug.assert_called_with("Failed to create Docker client: Connection failed")

    @patch("samcli.local.docker.container_client_factory.FinchContainerClient")
    def test_try_create_finch_client_success(self, mock_finch_class):
        """Test successful Finch client creation"""
        mock_client = Mock()
        mock_finch_class.return_value = mock_client

        result = ContainerClientFactory._try_create_finch_client()

        self.assertEqual(result, mock_client)
        mock_finch_class.assert_called_once_with()

    @patch("samcli.local.docker.container_client_factory.FinchContainerClient")
    def test_try_create_finch_client_exception(self, mock_finch_class):
        """Test Finch client creation when constructor fails"""
        mock_finch_class.side_effect = Exception("Finch not available")

        result = ContainerClientFactory._try_create_finch_client()

        self.assertIsNone(result)

    @patch("samcli.local.docker.container_client_factory.get_platform_handler")
    def test_get_error_message_with_handler(self, mock_get_handler):
        """Test getting error message with platform handler"""
        mock_handler = Mock()
        mock_handler.get_container_not_reachable_message.return_value = "Platform specific message"
        mock_get_handler.return_value = mock_handler

        result = ContainerClientFactory._get_error_message("Default message")

        self.assertEqual(result, "Platform specific message")

    @patch("samcli.local.docker.container_client_factory.get_platform_handler")
    def test_get_error_message_no_handler(self, mock_get_handler):
        """Test getting error message without platform handler"""
        mock_get_handler.return_value = None

        result = ContainerClientFactory._get_error_message("Default message")

        self.assertIn("Running AWS SAM projects locally requires", result)

    @patch("samcli.local.docker.container_client_factory.get_platform_handler")
    def test_admin_container_preference_valid(self, mock_get_handler):
        """Test admin container preference validation with valid preference"""
        mock_handler = Mock()
        mock_handler.read_config.return_value = "docker"
        mock_get_handler.return_value = mock_handler

        result = ContainerClientFactory.get_admin_container_preference()

        self.assertEqual(result, "docker")

    @patch("samcli.local.docker.container_client_factory.get_platform_handler")
    def test_admin_container_preference_invalid(self, mock_get_handler):
        """Test admin container preference validation with invalid preference"""
        mock_handler = Mock()
        mock_handler.read_config.return_value = "invalid"
        mock_get_handler.return_value = mock_handler

        result = ContainerClientFactory.get_admin_container_preference()

        self.assertIsNone(result)

    def test_get_validate_admin_container_preference_valid(self):
        """Test validating valid admin container preference"""
        with patch("samcli.cli.context.Context.get_current_context", return_value=Mock()):
            result = ContainerClientFactory._get_validate_admin_container_preference("Docker")
            self.assertEqual(result, "docker")

    def test_validate_admin_container_preference_invalid(self):
        """Test validating invalid admin container preference"""
        with patch("samcli.cli.context.Context.get_current_context", return_value=Mock()):
            result = ContainerClientFactory._get_validate_admin_container_preference("invalid")
            self.assertIsNone(result)

    def test_validate_admin_container_preference_none(self):
        """Test validating None admin container preference"""
        result = ContainerClientFactory._get_validate_admin_container_preference(None)
        self.assertIsNone(result)


class TestValidateAdminContainerPreference(TestCase):
    @parameterized.expand(
        [  # input_value, normalize_value, log_value
            ("finch", "finch", "Finch"),
            ("FINCH", "finch", "Finch"),
            ("Finch", "finch", "Finch"),
            ("  finch  ", "finch", "Finch"),
            ("docker", "docker", "Docker"),
            ("DOCKER", "docker", "Docker"),
            ("Docker", "docker", "Docker"),
            ("  docker  ", "docker", "Docker"),
        ]
    )
    @patch("samcli.local.docker.container_client_factory.set_container_socket_host_telemetry")
    @patch("samcli.local.docker.container_client_factory.LOG")
    def test_validate_admin_container_preference_valid_inputs(
        self, input_value, expected_output, log_value, mock_log, mock_set_telemetry
    ):
        """Test validation with valid container runtime inputs"""

        result = ContainerClientFactory._get_validate_admin_container_preference(input_value)
        self.assertEqual(result, expected_output)

        # Verify telemetry storage was called with the expected value
        mock_set_telemetry.assert_called_once_with(admin_preference=expected_output)

        mock_log.info.assert_has_calls(
            [
                call("Administrator container preference detected."),
                call("Valid administrator container preference: %s.", log_value),
            ]
        )

    @parameterized.expand(
        [
            ("podman",),
            ("containerd",),
            ("invalid",),
            ("INVALID",),
            ("123",),
            ("finch-invalid",),
            ("docker-test",),
        ]
    )
    @patch("samcli.local.docker.container_client_factory.set_container_socket_host_telemetry")
    @patch("samcli.local.docker.container_client_factory.LOG")
    def test_validate_admin_container_preference_invalid_inputs(self, input_value, mock_log, mock_set_telemetry):
        """Test validation with invalid container runtime inputs"""

        result = ContainerClientFactory._get_validate_admin_container_preference(input_value)
        self.assertIsNone(result)

        # Verify telemetry storage was called with "other" for invalid inputs
        mock_set_telemetry.assert_called_once_with(admin_preference="other")

        mock_log.info.assert_has_calls(
            [
                call("Administrator container preference detected."),
                call("Invalid administrator container preference: %s.", input_value),
            ]
        )

    @parameterized.expand([("",), ("   ",), (None)])
    @patch("samcli.local.docker.container_client_factory.LOG")
    def test_validate_admin_container_preference_none_input(self, input, mock_log):
        """Test validation with None input"""
        result = ContainerClientFactory._get_validate_admin_container_preference(input)
        self.assertIsNone(result)
        mock_log.warning.assert_not_called()


class TestAdminContainerPreference(TestCase):
    @parameterized.expand(
        [
            ("docker", "docker"),
            ("FINCH", "finch"),
        ]
    )
    @patch("samcli.local.docker.container_client_factory.set_container_socket_host_telemetry")
    @patch("samcli.local.docker.container_client_factory.LOG")
    @patch("samcli.local.docker.container_client_factory.get_platform_handler")
    def test_admin_preference_valid_inputs(
        self, raw_config, expected_result, mock_get_handler, mock_log, mock_set_telemetry
    ):
        """Test administrator preference verification logic with valid inputs"""
        mock_handler = Mock()
        mock_handler.read_config.return_value = raw_config
        mock_get_handler.return_value = mock_handler

        result = ContainerClientFactory.get_admin_container_preference()

        self.assertEqual(result, expected_result)
        mock_get_handler.assert_called_once()
        mock_handler.read_config.assert_called_once()

        # Verify telemetry storage was called with the expected value
        mock_set_telemetry.assert_called_once_with(admin_preference=expected_result)

        # Validate log messages and order
        mock_log.info.assert_has_calls(
            [
                call("Administrator container preference detected."),
                call("Valid administrator container preference: %s.", expected_result.capitalize()),
            ]
        )

    @parameterized.expand(
        [
            ("invalid",),
            ("podman",),
            ("containerd",),
        ]
    )
    @patch("samcli.local.docker.container_client_factory.set_container_socket_host_telemetry")
    @patch("samcli.local.docker.container_client_factory.LOG")
    @patch("samcli.local.docker.container_client_factory.get_platform_handler")
    def test_admin_preference_invalid_inputs(self, raw_config, mock_get_handler, mock_log, mock_set_telemetry):
        """Test administrator preference verification logic with invalid inputs"""
        mock_handler = Mock()
        mock_handler.read_config.return_value = raw_config
        mock_get_handler.return_value = mock_handler

        result = ContainerClientFactory.get_admin_container_preference()

        # Verify telemetry storage was called with "other" for invalid inputs
        mock_set_telemetry.assert_called_once_with(admin_preference="other")
        self.assertEqual(result, None)
        mock_log.info.assert_has_calls(
            [
                call("Administrator container preference detected."),
                call("Invalid administrator container preference: %s.", raw_config),
            ]
        )

    @patch("samcli.local.docker.container_client_factory.LOG")
    @patch("samcli.local.docker.container_client_factory.get_platform_handler")
    def test_admin_preference_returns_none_when_no_handler(self, mock_get_handler, mock_log):
        """Test administrator preference verification logic returns None when no platform handler available (unlikely)"""
        mock_get_handler.return_value = None

        result = ContainerClientFactory.get_admin_container_preference()

        self.assertEqual(result, None)
        mock_get_handler.assert_called_once()
        mock_log.info.assert_not_called()

    @patch("samcli.local.docker.container_client_factory.LOG")
    @patch("samcli.local.docker.container_client_factory.get_platform_handler")
    def test_admin_preference_returns_none_when_handler_returns_none(self, mock_get_handler, mock_log):
        """Test administrator preference verification logic returns None when handler returns no config"""
        mock_handler = Mock()
        mock_handler.read_config.return_value = None
        mock_get_handler.return_value = mock_handler

        result = ContainerClientFactory.get_admin_container_preference()

        self.assertEqual(result, None)
        mock_handler.read_config.assert_called_once()
        mock_log.info.assert_not_called()


# TestSetContextRuntimeType and TestCreateClientWithContextStorage classes removed
# These tests are no longer relevant since _set_context_runtime_type method was removed
# in favor of the new global telemetry storage approach


class TestCreateClientIntegration(TestCase):
    """Integration tests for create_client method - tests the real method by mocking its dependencies"""

    @parameterized.expand(
        [
            # (docker_available, finch_available, expected_engine)
            (True, False, "docker"),
            (False, True, "finch"),
            (True, True, "docker"),  # Docker has priority when both available
        ]
    )
    @patch("samcli.local.docker.container_client_factory.ContainerClientFactory.get_admin_container_preference")
    @patch("samcli.local.docker.container_client_factory.ContainerClientFactory._try_create_docker_client")
    @patch("samcli.local.docker.container_client_factory.ContainerClientFactory._try_create_finch_client")
    @patch("samcli.local.docker.container_client_factory.LOG")
    def test_create_client_auto_detection_success(
        self,
        docker_available,
        finch_available,
        expected_engine,
        mock_log,
        mock_try_finch,
        mock_try_docker,
        mock_get_preference,
    ):
        """Test create_client with auto-detection when no admin preference is set"""
        # No admin preference
        mock_get_preference.return_value = None

        # Setup Docker client mock
        docker_client = Mock() if docker_available else None
        if docker_client:
            docker_client.is_available.return_value = docker_available
        mock_try_docker.return_value = docker_client

        # Setup Finch client mock
        finch_client = Mock() if finch_available else None
        if finch_client:
            finch_client.is_available.return_value = finch_available
        mock_try_finch.return_value = finch_client

        # Execute
        result = ContainerClientFactory.create_client()

        # Verify
        if expected_engine == "docker":
            self.assertEqual(result, docker_client)
            mock_log.debug.assert_called_with("Using Docker as Container Engine.")
        else:
            self.assertEqual(result, finch_client)
            mock_log.debug.assert_called_with("Using Finch as Container Engine.")

    @parameterized.expand(
        [
            ("docker", "docker"),
            ("finch", "finch"),
        ]
    )
    @patch("samcli.local.docker.container_client_factory.ContainerClientFactory.get_admin_container_preference")
    @patch("samcli.local.docker.container_client_factory.ContainerClientFactory._try_create_docker_client")
    @patch("samcli.local.docker.container_client_factory.ContainerClientFactory._try_create_finch_client")
    @patch("samcli.local.docker.container_client_factory.LOG")
    def test_create_client_with_admin_preference_success(
        self,
        preference,
        expected_engine,
        mock_log,
        mock_try_finch,
        mock_try_docker,
        mock_get_preference,
    ):
        """Test create_client with valid admin preference"""
        # Set admin preference
        mock_get_preference.return_value = preference

        # Setup client mocks - both available
        docker_client = Mock()
        docker_client.is_available.return_value = True
        mock_try_docker.return_value = docker_client

        finch_client = Mock()
        finch_client.is_available.return_value = True
        mock_try_finch.return_value = finch_client

        # Execute
        result = ContainerClientFactory.create_client()

        # Verify correct client is returned based on preference
        if expected_engine == "docker":
            self.assertEqual(result, docker_client)
            mock_log.debug.assert_called_with("Using Docker as Container Engine (enforced).")
        else:
            self.assertEqual(result, finch_client)
            mock_log.debug.assert_called_with("Using Finch as Container Engine (enforced).")

    @patch("samcli.local.docker.container_client_factory.ContainerClientFactory.get_admin_container_preference")
    @patch("samcli.local.docker.container_client_factory.ContainerClientFactory._try_create_docker_client")
    @patch("samcli.local.docker.container_client_factory.ContainerClientFactory._try_create_finch_client")
    @patch("samcli.local.docker.container_client_factory.ContainerClientFactory._get_error_message")
    def test_create_client_no_containers_available(
        self,
        mock_get_error,
        mock_try_finch,
        mock_try_docker,
        mock_get_preference,
    ):
        """Test create_client when no container runtimes are available"""
        # No admin preference
        mock_get_preference.return_value = None

        # No containers available
        mock_try_docker.return_value = None
        mock_try_finch.return_value = None
        mock_get_error.return_value = "No container runtime available"

        # Execute and verify exception
        with self.assertRaises(ContainerNotReachableException):
            ContainerClientFactory.create_client()

    @parameterized.expand(
        [
            ("docker",),
            ("finch",),
        ]
    )
    @patch("samcli.local.docker.container_client_factory.ContainerClientFactory.get_admin_container_preference")
    @patch("samcli.local.docker.container_client_factory.ContainerClientFactory._try_create_docker_client")
    @patch("samcli.local.docker.container_client_factory.ContainerClientFactory._try_create_finch_client")
    @patch("samcli.local.docker.container_client_factory.ContainerClientFactory._get_error_message")
    def test_create_client_admin_preference_unavailable(
        self,
        preference,
        mock_get_error,
        mock_try_finch,
        mock_try_docker,
        mock_get_preference,
    ):
        """Test create_client when admin preferred container is unavailable"""
        # Set admin preference
        mock_get_preference.return_value = preference

        # Setup unavailable client
        if preference == "docker":
            unavailable_client = Mock()
            unavailable_client.is_available.return_value = False
            mock_try_docker.return_value = unavailable_client
        else:
            unavailable_client = Mock()
            unavailable_client.is_available.return_value = False
            mock_try_finch.return_value = unavailable_client

        mock_get_error.return_value = f"{preference.capitalize()} not available"

        # Execute and verify exception
        with self.assertRaises(ContainerEnforcementException):
            ContainerClientFactory.create_client()
