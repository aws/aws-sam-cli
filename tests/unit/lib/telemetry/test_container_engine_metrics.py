"""
Unit tests for container engine metrics collection
"""

import os
from unittest import TestCase
from unittest.mock import patch, Mock, ANY
from parameterized import parameterized

from samcli.lib.telemetry.metric import _send_command_run_metrics, Metric


class MockContext:
    """Simple context object for testing"""

    def __init__(self):
        self.profile = None
        self.debug = False
        self.region = "us-east-1"
        self.command_path = "sam local start-api"
        self.experimental = False
        self.template_dict = {}
        self.session_id = "test-session-id"


class TestContainerEngineMetrics(TestCase):
    def setUp(self):
        self.mock_ctx = MockContext()

    @parameterized.expand(
        [
            # (socket_path, expected_engine, test_description)
            ("unix://~/.finch/finch.sock", "finch", "Finch container engine from global storage"),
            ("unix://~/.rd/docker.sock", "rancher-desktop", "Rancher Desktop container engine from global storage"),
        ]
    )
    @patch("samcli.lib.telemetry.metric.get_container_runtime_telemetry_info")
    @patch("samcli.lib.telemetry.metric.Telemetry")
    @patch("samcli.lib.telemetry.event.EventTracker.send_events")
    @patch("samcli.lib.telemetry.metric.get_all_experimental_statues")
    @patch("samcli.lib.telemetry.metric.get_git_remote_origin_url")
    @patch("samcli.lib.telemetry.metric.get_project_name")
    @patch("samcli.lib.telemetry.metric.get_initial_commit_hash")
    def test_container_engine_from_global_storage_scenarios(
        self,
        socket_path,
        expected_engine,
        description,
        mock_initial_commit,
        mock_project_name,
        mock_git_origin,
        mock_experimental,
        mock_send_events,
        mock_telemetry,
        mock_get_runtime_info,
    ):
        """Test that container engine is retrieved from global storage for various engines"""
        # Setup mocks
        mock_experimental.return_value = {}
        mock_git_origin.return_value = "origin"
        mock_project_name.return_value = "test-project"
        mock_initial_commit.return_value = "abc123"

        # Mock global storage to return the specified socket
        mock_get_runtime_info.return_value = {
            "container_socket_path": socket_path,
            "admin_preference": None,
        }

        self.mock_ctx.template_dict = {}

        # Call the function
        _send_command_run_metrics(self.mock_ctx, 1000, "success", 0)

        # Verify telemetry was called
        mock_telemetry.assert_called_once()
        telemetry_instance = mock_telemetry.return_value
        telemetry_instance.emit.assert_called_once()

        # Get the metric that was emitted
        metric_call_args = telemetry_instance.emit.call_args[0]
        metric = metric_call_args[0]
        metric_data = metric.get_data()

        # Verify container engine is correctly reported
        self.assertIn("metricSpecificAttributes", metric_data)
        metric_attrs = metric_data["metricSpecificAttributes"]
        self.assertEqual(metric_attrs["containerEngine"], expected_engine, f"Failed for {description}")

    @parameterized.expand(
        [
            # (docker_host_env, expected_engine, test_description)
            ({"DOCKER_HOST": "unix:///var/run/docker.sock"}, "docker", "Docker fallback via DOCKER_HOST"),
            ({"DOCKER_HOST": "unix://~/.colima/default/docker.sock"}, "colima", "Colima fallback via DOCKER_HOST"),
            ({}, "docker-default", "docker-default when no DOCKER_HOST"),
        ]
    )
    @patch("samcli.lib.telemetry.metric.get_container_runtime_telemetry_info")
    @patch("samcli.cli.context.Context.get_current_context")
    @patch("samcli.lib.telemetry.metric.Telemetry")
    @patch("samcli.lib.telemetry.event.EventTracker.send_events")
    @patch("samcli.lib.telemetry.metric.get_all_experimental_statues")
    @patch("samcli.lib.telemetry.metric.get_git_remote_origin_url")
    @patch("samcli.lib.telemetry.metric.get_project_name")
    @patch("samcli.lib.telemetry.metric.get_initial_commit_hash")
    @patch.dict("os.environ", {}, clear=True)
    def test_container_engine_fallback_scenarios(
        self,
        docker_host_env,
        expected_engine,
        description,
        mock_initial_commit,
        mock_project_name,
        mock_git_origin,
        mock_experimental,
        mock_send_events,
        mock_telemetry,
        mock_get_context,
        mock_get_runtime_info,
    ):
        """Test that container engine falls back to DOCKER_HOST detection for various scenarios"""
        # Setup mocks
        mock_experimental.return_value = {}
        mock_git_origin.return_value = "origin"
        mock_project_name.return_value = "test-project"
        mock_initial_commit.return_value = "abc123"

        # Mock global storage to return empty values (forcing fallback to DOCKER_HOST)
        mock_get_runtime_info.return_value = {
            "container_socket_path": None,
            "admin_preference": None,
        }

        # No actual container runtime in context (fallback scenario)
        self.mock_ctx.template_dict = {}

        # Mock the context access for the Metric instance
        mock_get_context.return_value = self.mock_ctx

        # Call the function with the specified environment
        with patch.dict("os.environ", docker_host_env):
            _send_command_run_metrics(self.mock_ctx, 1000, "success", 0)

        # Verify telemetry was called
        mock_telemetry.assert_called_once()
        telemetry_instance = mock_telemetry.return_value
        telemetry_instance.emit.assert_called_once()

        # Get the metric that was emitted
        metric_call_args = telemetry_instance.emit.call_args[0]
        metric = metric_call_args[0]
        metric_data = metric.get_data()

        # Verify container engine is correctly detected
        self.assertIn("metricSpecificAttributes", metric_data)
        metric_attrs = metric_data["metricSpecificAttributes"]
        self.assertEqual(metric_attrs["containerEngine"], expected_engine, f"Failed for {description}")


class TestMetricGetContainerHost(TestCase):
    """Test the _get_container_host method directly"""

    def setUp(self):
        self.metric = Metric("test", should_add_common_attributes=False)

    @parameterized.expand(
        [
            # (socket_path, admin_preference, expected_result, test_description)
            ("unix://~/.finch/finch.sock", None, "finch", "Finch socket from global storage"),
            ("unix:///var/run/docker.sock", None, "docker", "Docker socket from global storage"),
            (None, None, "docker-default", "no socket path in global storage"),
            ("", "", "docker-default", "empty values in global storage"),
        ]
    )
    @patch("samcli.lib.telemetry.metric.get_container_runtime_telemetry_info")
    @patch.dict("os.environ", {}, clear=True)
    def test_get_container_host_from_global_storage_scenarios(
        self, socket_path, admin_preference, expected_result, description, mock_get_runtime_info
    ):
        """Test getting container host from global storage with various scenarios"""
        mock_get_runtime_info.return_value = {
            "container_socket_path": socket_path,
            "admin_preference": admin_preference,
        }

        result = self.metric._get_container_host()

        self.assertEqual(result, expected_result, f"Failed for {description}")

    @parameterized.expand(
        [
            # (socket_path, expected_result, test_description)
            ("unix:///var/run/docker.sock", "docker", "Docker socket"),
            ("unix://~/.finch/finch.sock", "finch", "Finch socket"),
            ("unix://~/.colima/default/docker.sock", "colima", "Colima socket"),
            ("unix://~/.lima/default/sock/docker.sock", "lima", "Lima socket"),
            ("unix://~/.orbstack/run/docker.sock", "orbstack", "OrbStack socket"),
            ("unix://~/.rd/docker.sock", "rancher-desktop", "Rancher Desktop socket"),
            ("unix:///run/user/1000/podman/podman.sock", "podman", "Podman socket"),
            ("tcp://localhost:2375", "tcp-local", "TCP local connection"),
            ("tcp://remote.example.com:2376", "tcp-remote", "TCP remote connection"),
            ("unknown://some.socket", "unknown", "unknown protocol"),
            ("", "docker-default", "empty socket path"),
        ]
    )
    def test_get_container_engine_from_socket_path_scenarios(self, socket_path, expected_result, description):
        """Test getting container engine from socket path with various values"""
        result = self.metric._get_container_engine_from_socket_path(socket_path)
        self.assertEqual(result, expected_result, f"Failed for {description}")

    @patch("samcli.lib.telemetry.metric.get_container_runtime_telemetry_info")
    @patch.dict("os.environ", {}, clear=True)
    def test_get_container_host_no_docker_host(self, mock_get_runtime_info):
        """Test getting container host when no DOCKER_HOST set and no global storage"""
        mock_get_runtime_info.return_value = {"container_socket_path": None, "admin_preference": None}

        result = self.metric._get_container_host()
        self.assertEqual(result, "docker-default")
