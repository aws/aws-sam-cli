"""
Unit tests for admin container preference metrics collection
"""

from unittest import TestCase
from unittest.mock import patch, Mock, ANY

from samcli.lib.telemetry.metric import _send_command_run_metrics


class MockContext:
    """Simple context object for testing"""

    def __init__(self):
        self.profile = None
        self.debug = False
        self.region = "us-east-1"
        self.command_path = "sam local start-api"
        self.experimental = False
        self.template_dict = {}


class TestAdminPreferenceMetrics(TestCase):
    def setUp(self):
        self.mock_ctx = MockContext()

    @patch("samcli.lib.telemetry.metric.Telemetry")
    @patch("samcli.lib.telemetry.event.EventTracker.send_events")
    @patch("samcli.lib.telemetry.metric.get_all_experimental_statues")
    @patch("samcli.lib.telemetry.metric.get_git_remote_origin_url")
    @patch("samcli.lib.telemetry.metric.get_project_name")
    @patch("samcli.lib.telemetry.metric.get_initial_commit_hash")
    def test_admin_preference_from_context(
        self,
        mock_initial_commit,
        mock_project_name,
        mock_git_origin,
        mock_experimental,
        mock_send_events,
        mock_telemetry,
    ):
        """Test that admin preference is retrieved from context when available"""
        # Setup mocks
        mock_experimental.return_value = {}
        mock_git_origin.return_value = "origin"
        mock_project_name.return_value = "test-project"
        mock_initial_commit.return_value = "abc123"

        # Set admin preference in context
        self.mock_ctx.admin_container_preference = "finch"

        # Mock template_dict to avoid AttributeError
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

        # Verify admin preference is in metricSpecificAttributes
        self.assertIn("metricSpecificAttributes", metric_data)
        metric_attrs = metric_data["metricSpecificAttributes"]
        self.assertEqual(metric_attrs["adminContainerPreference"], "finch")

    @patch("samcli.lib.telemetry.metric.Telemetry")
    @patch("samcli.lib.telemetry.event.EventTracker.send_events")
    @patch("samcli.lib.telemetry.metric.get_all_experimental_statues")
    @patch("samcli.lib.telemetry.metric.get_git_remote_origin_url")
    @patch("samcli.lib.telemetry.metric.get_project_name")
    @patch("samcli.lib.telemetry.metric.get_initial_commit_hash")
    def test_admin_preference_fallback(
        self,
        mock_initial_commit,
        mock_project_name,
        mock_git_origin,
        mock_experimental,
        mock_send_events,
        mock_telemetry,
    ):
        """Test that admin preference is not read when not in context (no fallback)"""
        # Setup mocks
        mock_experimental.return_value = {}
        mock_git_origin.return_value = "origin"
        mock_project_name.return_value = "test-project"
        mock_initial_commit.return_value = "abc123"

        # No admin preference in context
        self.mock_ctx.admin_container_preference = None
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

        # Verify admin preference field is None when not in context
        self.assertIn("metricSpecificAttributes", metric_data)
        metric_attrs = metric_data["metricSpecificAttributes"]
        self.assertEqual(metric_attrs["adminContainerPreference"], None)

    @patch("samcli.lib.telemetry.metric.Telemetry")
    @patch("samcli.lib.telemetry.event.EventTracker.send_events")
    @patch("samcli.lib.telemetry.metric.get_all_experimental_statues")
    @patch("samcli.lib.telemetry.metric.get_git_remote_origin_url")
    @patch("samcli.lib.telemetry.metric.get_project_name")
    @patch("samcli.lib.telemetry.metric.get_initial_commit_hash")
    @patch("samcli.local.docker.container_client_factory.ContainerClientFactory.get_admin_container_preference")
    def test_admin_preference_none_fallback(
        self,
        mock_admin_pref,
        mock_initial_commit,
        mock_project_name,
        mock_git_origin,
        mock_experimental,
        mock_send_events,
        mock_telemetry,
    ):
        """Test that None admin preference is not included in metrics"""
        # Setup mocks
        mock_experimental.return_value = {}
        mock_git_origin.return_value = "origin"
        mock_project_name.return_value = "test-project"
        mock_initial_commit.return_value = "abc123"
        mock_admin_pref.return_value = None

        # No admin preference in context
        self.mock_ctx.admin_container_preference = None
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

        # Verify admin preference field is None when None
        self.assertIn("metricSpecificAttributes", metric_data)
        metric_attrs = metric_data["metricSpecificAttributes"]
        self.assertEqual(metric_attrs["adminContainerPreference"], None)

    @patch("samcli.lib.telemetry.metric.Telemetry")
    @patch("samcli.lib.telemetry.event.EventTracker.send_events")
    @patch("samcli.lib.telemetry.metric.get_all_experimental_statues")
    @patch("samcli.lib.telemetry.metric.get_git_remote_origin_url")
    @patch("samcli.lib.telemetry.metric.get_project_name")
    @patch("samcli.lib.telemetry.metric.get_initial_commit_hash")
    def test_admin_preference_no_attribute(
        self,
        mock_initial_commit,
        mock_project_name,
        mock_git_origin,
        mock_experimental,
        mock_send_events,
        mock_telemetry,
    ):
        """Test that admin preference defaults to None when attribute doesn't exist"""
        # Setup mocks
        mock_experimental.return_value = {}
        mock_git_origin.return_value = "origin"
        mock_project_name.return_value = "test-project"
        mock_initial_commit.return_value = "abc123"

        # Don't set admin_container_preference attribute at all
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

        # Verify admin preference field defaults to None when attribute missing
        self.assertIn("metricSpecificAttributes", metric_data)
        metric_attrs = metric_data["metricSpecificAttributes"]
        self.assertEqual(metric_attrs["adminContainerPreference"], None)
