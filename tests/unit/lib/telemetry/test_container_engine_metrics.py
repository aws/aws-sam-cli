"""
Unit tests for container engine metrics collection
"""

import os
from unittest import TestCase
from unittest.mock import patch, Mock, ANY

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

    @patch("samcli.cli.context.Context.get_current_context")
    @patch("samcli.lib.telemetry.metric.Telemetry")
    @patch("samcli.lib.telemetry.event.EventTracker.send_events")
    @patch("samcli.lib.telemetry.metric.get_all_experimental_statues")
    @patch("samcli.lib.telemetry.metric.get_git_remote_origin_url")
    @patch("samcli.lib.telemetry.metric.get_project_name")
    @patch("samcli.lib.telemetry.metric.get_initial_commit_hash")
    def test_container_engine_from_context_finch(
        self,
        mock_initial_commit,
        mock_project_name,
        mock_git_origin,
        mock_experimental,
        mock_send_events,
        mock_telemetry,
        mock_get_context,
    ):
        """Test that container engine is retrieved from context when Finch is used"""
        # Setup mocks
        mock_experimental.return_value = {}
        mock_git_origin.return_value = "origin"
        mock_project_name.return_value = "test-project"
        mock_initial_commit.return_value = "abc123"

        # Set actual container runtime in context
        self.mock_ctx.actual_container_runtime = "finch"
        self.mock_ctx.template_dict = {}

        # Mock the context access for the Metric instance
        mock_get_context.return_value = self.mock_ctx

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

        # Verify container engine is correctly reported as finch
        self.assertIn("metricSpecificAttributes", metric_data)
        metric_attrs = metric_data["metricSpecificAttributes"]
        self.assertEqual(metric_attrs["containerEngine"], "finch")

    @patch("samcli.cli.context.Context.get_current_context")
    @patch("samcli.lib.telemetry.metric.Telemetry")
    @patch("samcli.lib.telemetry.event.EventTracker.send_events")
    @patch("samcli.lib.telemetry.metric.get_all_experimental_statues")
    @patch("samcli.lib.telemetry.metric.get_git_remote_origin_url")
    @patch("samcli.lib.telemetry.metric.get_project_name")
    @patch("samcli.lib.telemetry.metric.get_initial_commit_hash")
    def test_container_engine_from_context_docker(
        self,
        mock_initial_commit,
        mock_project_name,
        mock_git_origin,
        mock_experimental,
        mock_send_events,
        mock_telemetry,
        mock_get_context,
    ):
        """Test that container engine is retrieved from context when Docker is used"""
        # Setup mocks
        mock_experimental.return_value = {}
        mock_git_origin.return_value = "origin"
        mock_project_name.return_value = "test-project"
        mock_initial_commit.return_value = "abc123"

        # Set actual container runtime in context
        self.mock_ctx.actual_container_runtime = "rancher-desktop"
        self.mock_ctx.template_dict = {}

        # Mock the context access for the Metric instance
        mock_get_context.return_value = self.mock_ctx

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

        # Verify container engine is correctly reported as docker
        self.assertIn("metricSpecificAttributes", metric_data)
        metric_attrs = metric_data["metricSpecificAttributes"]
        self.assertEqual(metric_attrs["containerEngine"], "rancher-desktop")

    @patch("samcli.cli.context.Context.get_current_context")
    @patch("samcli.lib.telemetry.metric.Telemetry")
    @patch("samcli.lib.telemetry.event.EventTracker.send_events")
    @patch("samcli.lib.telemetry.metric.get_all_experimental_statues")
    @patch("samcli.lib.telemetry.metric.get_git_remote_origin_url")
    @patch("samcli.lib.telemetry.metric.get_project_name")
    @patch("samcli.lib.telemetry.metric.get_initial_commit_hash")
    @patch.dict("os.environ", {}, clear=True)
    def test_container_engine_fallback_to_docker_host_docker(
        self,
        mock_initial_commit,
        mock_project_name,
        mock_git_origin,
        mock_experimental,
        mock_send_events,
        mock_telemetry,
        mock_get_context,
    ):
        """Test that container engine falls back to DOCKER_HOST detection for Docker"""
        # Setup mocks
        mock_experimental.return_value = {}
        mock_git_origin.return_value = "origin"
        mock_project_name.return_value = "test-project"
        mock_initial_commit.return_value = "abc123"

        # No actual container runtime in context (fallback scenario)
        self.mock_ctx.template_dict = {}

        # Mock the context access for the Metric instance
        mock_get_context.return_value = self.mock_ctx

        # Call the function with DOCKER_HOST set
        with patch.dict("os.environ", {"DOCKER_HOST": "unix:///var/run/docker.sock"}):
            _send_command_run_metrics(self.mock_ctx, 1000, "success", 0)

        # Verify telemetry was called
        mock_telemetry.assert_called_once()
        telemetry_instance = mock_telemetry.return_value
        telemetry_instance.emit.assert_called_once()

        # Get the metric that was emitted
        metric_call_args = telemetry_instance.emit.call_args[0]
        metric = metric_call_args[0]
        metric_data = metric.get_data()

        # Verify container engine falls back to DOCKER_HOST detection
        self.assertIn("metricSpecificAttributes", metric_data)
        metric_attrs = metric_data["metricSpecificAttributes"]
        self.assertEqual(metric_attrs["containerEngine"], "docker")

    @patch("samcli.cli.context.Context.get_current_context")
    @patch("samcli.lib.telemetry.metric.Telemetry")
    @patch("samcli.lib.telemetry.event.EventTracker.send_events")
    @patch("samcli.lib.telemetry.metric.get_all_experimental_statues")
    @patch("samcli.lib.telemetry.metric.get_git_remote_origin_url")
    @patch("samcli.lib.telemetry.metric.get_project_name")
    @patch("samcli.lib.telemetry.metric.get_initial_commit_hash")
    @patch.dict("os.environ", {}, clear=True)
    def test_container_engine_fallback_to_docker_host_colima(
        self,
        mock_initial_commit,
        mock_project_name,
        mock_git_origin,
        mock_experimental,
        mock_send_events,
        mock_telemetry,
        mock_get_context,
    ):
        """Test that container engine falls back to DOCKER_HOST detection for Colima"""
        # Setup mocks
        mock_experimental.return_value = {}
        mock_git_origin.return_value = "origin"
        mock_project_name.return_value = "test-project"
        mock_initial_commit.return_value = "abc123"

        # No actual container runtime in context (fallback scenario)
        self.mock_ctx.template_dict = {}

        # Mock the context access for the Metric instance
        mock_get_context.return_value = self.mock_ctx

        # Call the function with DOCKER_HOST set
        with patch.dict("os.environ", {"DOCKER_HOST": "unix://~/.colima/default/docker.sock"}):
            _send_command_run_metrics(self.mock_ctx, 1000, "success", 0)

        # Verify telemetry was called
        mock_telemetry.assert_called_once()
        telemetry_instance = mock_telemetry.return_value
        telemetry_instance.emit.assert_called_once()

        # Get the metric that was emitted
        metric_call_args = telemetry_instance.emit.call_args[0]
        metric = metric_call_args[0]
        metric_data = metric.get_data()

        # Verify container engine falls back to DOCKER_HOST detection for Colima
        self.assertIn("metricSpecificAttributes", metric_data)
        metric_attrs = metric_data["metricSpecificAttributes"]
        self.assertEqual(metric_attrs["containerEngine"], "colima")

    @patch("samcli.cli.context.Context.get_current_context")
    @patch("samcli.lib.telemetry.metric.Telemetry")
    @patch("samcli.lib.telemetry.event.EventTracker.send_events")
    @patch("samcli.lib.telemetry.metric.get_all_experimental_statues")
    @patch("samcli.lib.telemetry.metric.get_git_remote_origin_url")
    @patch("samcli.lib.telemetry.metric.get_project_name")
    @patch("samcli.lib.telemetry.metric.get_initial_commit_hash")
    @patch.dict("os.environ", {}, clear=True)
    def test_container_engine_fallback_to_docker_default(
        self,
        mock_initial_commit,
        mock_project_name,
        mock_git_origin,
        mock_experimental,
        mock_send_events,
        mock_telemetry,
        mock_get_context,
    ):
        """Test that container engine falls back to docker-default when no DOCKER_HOST"""
        # Setup mocks
        mock_experimental.return_value = {}
        mock_git_origin.return_value = "origin"
        mock_project_name.return_value = "test-project"
        mock_initial_commit.return_value = "abc123"

        # No actual container runtime in context (fallback scenario)
        self.mock_ctx.template_dict = {}

        # Mock the context access for the Metric instance
        mock_get_context.return_value = self.mock_ctx

        # Call the function with no DOCKER_HOST set (already cleared by decorator)
        _send_command_run_metrics(self.mock_ctx, 1000, "success", 0)

        # Verify telemetry was called
        mock_telemetry.assert_called_once()
        telemetry_instance = mock_telemetry.return_value
        telemetry_instance.emit.assert_called_once()

        # Get the metric that was emitted
        metric_call_args = telemetry_instance.emit.call_args[0]
        metric = metric_call_args[0]
        metric_data = metric.get_data()

        # Verify container engine falls back to docker-default
        self.assertIn("metricSpecificAttributes", metric_data)
        metric_attrs = metric_data["metricSpecificAttributes"]
        self.assertEqual(metric_attrs["containerEngine"], "docker-default")


class TestMetricGetContainerHost(TestCase):
    """Test the _get_container_host method directly"""

    def setUp(self):
        self.metric = Metric("test", should_add_common_attributes=False)

    @patch("samcli.cli.context.Context.get_current_context")
    def test_get_container_host_from_context_finch(self, mock_get_context):
        """Test getting container host from context when Finch is stored"""
        mock_ctx = Mock()
        mock_ctx.actual_container_runtime = "finch"
        mock_get_context.return_value = mock_ctx

        result = self.metric._get_container_host()

        self.assertEqual(result, "finch")

    @patch("samcli.cli.context.Context.get_current_context")
    def test_get_container_host_from_context_docker(self, mock_get_context):
        """Test getting container host from context when Docker is stored"""
        mock_ctx = Mock()
        mock_ctx.actual_container_runtime = "docker"
        mock_get_context.return_value = mock_ctx

        result = self.metric._get_container_host()

        self.assertEqual(result, "docker")

    @patch("samcli.cli.context.Context.get_current_context")
    def test_get_container_host_no_context_attribute(self, mock_get_context):
        """Test getting container host when no actual_container_runtime in context"""
        mock_ctx = Mock()
        # Don't set actual_container_runtime attribute
        del mock_ctx.actual_container_runtime
        mock_get_context.return_value = mock_ctx

        with patch.object(self.metric, "_get_container_host_from_env", return_value="docker-default") as mock_env:
            result = self.metric._get_container_host()

        self.assertEqual(result, "docker-default")
        mock_env.assert_called_once()

    @patch("samcli.cli.context.Context.get_current_context")
    def test_get_container_host_context_runtime_error(self, mock_get_context):
        """Test getting container host when context raises RuntimeError"""
        mock_get_context.side_effect = RuntimeError("No context available")

        with patch.object(self.metric, "_get_container_host_from_env", return_value="docker-default") as mock_env:
            result = self.metric._get_container_host()

        self.assertEqual(result, "docker-default")
        mock_env.assert_called_once()

    @patch.dict("os.environ", {}, clear=True)
    def test_get_container_host_from_env_docker(self):
        """Test getting container host from environment for Docker"""
        with patch.dict("os.environ", {"DOCKER_HOST": "unix:///var/run/docker.sock"}):
            result = self.metric._get_container_host_from_env()
            self.assertEqual(result, "docker")

    @patch.dict("os.environ", {}, clear=True)
    def test_get_container_host_from_env_finch(self):
        """Test getting container host from environment for Finch"""
        with patch.dict("os.environ", {"DOCKER_HOST": "unix://~/.finch/finch.sock"}):
            result = self.metric._get_container_host_from_env()
            self.assertEqual(result, "finch")

    @patch.dict("os.environ", {}, clear=True)
    def test_get_container_host_from_env_colima(self):
        """Test getting container host from environment for Colima"""
        with patch.dict("os.environ", {"DOCKER_HOST": "unix://~/.colima/default/docker.sock"}):
            result = self.metric._get_container_host_from_env()
            self.assertEqual(result, "colima")

    @patch.dict("os.environ", {}, clear=True)
    def test_get_container_host_from_env_lima(self):
        """Test getting container host from environment for Lima"""
        with patch.dict("os.environ", {"DOCKER_HOST": "unix://~/.lima/default/sock/docker.sock"}):
            result = self.metric._get_container_host_from_env()
            self.assertEqual(result, "lima")

    @patch.dict("os.environ", {}, clear=True)
    def test_get_container_host_from_env_orbstack(self):
        """Test getting container host from environment for OrbStack"""
        with patch.dict("os.environ", {"DOCKER_HOST": "unix://~/.orbstack/run/docker.sock"}):
            result = self.metric._get_container_host_from_env()
            self.assertEqual(result, "orbstack")

    @patch.dict("os.environ", {}, clear=True)
    def test_get_container_host_from_env_rancher_desktop(self):
        """Test getting container host from environment for Rancher Desktop"""
        with patch.dict("os.environ", {"DOCKER_HOST": "unix://~/.rd/docker.sock"}):
            result = self.metric._get_container_host_from_env()
            self.assertEqual(result, "rancher-desktop")

    @patch.dict("os.environ", {}, clear=True)
    def test_get_container_host_from_env_podman(self):
        """Test getting container host from environment for Podman"""
        with patch.dict("os.environ", {"DOCKER_HOST": "unix:///run/user/1000/podman/podman.sock"}):
            result = self.metric._get_container_host_from_env()
            self.assertEqual(result, "podman")

    @patch.dict("os.environ", {}, clear=True)
    def test_get_container_host_from_env_tcp_local(self):
        """Test getting container host from environment for TCP local"""
        with patch.dict("os.environ", {"DOCKER_HOST": "tcp://localhost:2375"}):
            result = self.metric._get_container_host_from_env()
            self.assertEqual(result, "tcp-local")

    @patch.dict("os.environ", {}, clear=True)
    def test_get_container_host_from_env_tcp_remote(self):
        """Test getting container host from environment for TCP remote"""
        with patch.dict("os.environ", {"DOCKER_HOST": "tcp://remote.example.com:2376"}):
            result = self.metric._get_container_host_from_env()
            self.assertEqual(result, "tcp-remote")

    @patch.dict("os.environ", {}, clear=True)
    def test_get_container_host_from_env_unknown(self):
        """Test getting container host from environment for unknown protocol"""
        with patch.dict("os.environ", {"DOCKER_HOST": "unknown://some.socket"}):
            result = self.metric._get_container_host_from_env()
            self.assertEqual(result, "unknown")

    @patch.dict("os.environ", {}, clear=True)
    def test_get_container_host_from_env_no_docker_host(self):
        """Test getting container host from environment when DOCKER_HOST not set"""
        result = self.metric._get_container_host_from_env()
        self.assertEqual(result, "docker-default")
