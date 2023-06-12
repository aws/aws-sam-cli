from unittest import TestCase
from unittest.mock import Mock, patch
from uuid import uuid4

from samcli.commands.remote.exceptions import (
    InvalidRemoteInvokeParameters,
    AmbiguousResourceForRemoteInvoke,
    NoResourceFoundForRemoteInvoke,
    UnsupportedServiceForRemoteInvoke,
    NoExecutorFoundForRemoteInvoke,
    InvalidStackNameProvidedForRemoteInvoke,
)
from samcli.commands.remote.remote_invoke_context import RemoteInvokeContext, SUPPORTED_SERVICES
from samcli.lib.utils.cloudformation import CloudFormationResourceSummary


class TestRemoteInvokeContext(TestCase):
    def setUp(self) -> None:
        self.boto_client_provider = Mock()
        self.boto_resource_provider = Mock()
        self.stack_name = uuid4().hex
        self.resource_id = uuid4().hex

    def _get_remote_invoke_context(self):
        return RemoteInvokeContext(
            self.boto_client_provider, self.boto_resource_provider, self.stack_name, self.resource_id
        )

    def test_no_stack_name_and_no_resource_id_should_fail(self):
        self.resource_id = None
        self.stack_name = None
        with self.assertRaises(InvalidRemoteInvokeParameters):
            with self._get_remote_invoke_context():
                pass

    @patch("samcli.commands.remote.remote_invoke_context.get_resource_summaries")
    def test_invalid_stack_name_with_no_resource_should_fail(self, patched_resource_summaries):
        self.resource_id = None
        patched_resource_summaries.side_effect = InvalidStackNameProvidedForRemoteInvoke("Invalid stack-name")
        with self.assertRaises(InvalidStackNameProvidedForRemoteInvoke):
            with self._get_remote_invoke_context():
                pass

    @patch("samcli.commands.remote.remote_invoke_context.get_resource_summaries")
    def test_only_stack_name_with_no_resource_should_fail(self, patched_resource_summaries):
        self.resource_id = None
        patched_resource_summaries.return_value = {}
        with self.assertRaises(NoResourceFoundForRemoteInvoke):
            with self._get_remote_invoke_context():
                pass

    @patch("samcli.commands.remote.remote_invoke_context.get_resource_summaries")
    def test_only_stack_name_with_multiple_resource_should_fail(self, patched_resource_summaries):
        self.resource_id = None
        patched_resource_summaries.return_value = {"resource1": Mock(), "resource2": Mock()}
        with self.assertRaises(AmbiguousResourceForRemoteInvoke):
            with self._get_remote_invoke_context():
                pass

    @patch("samcli.commands.remote.remote_invoke_context.get_resource_summaries")
    def test_only_stack_name_with_single_resource_should_be_valid(self, patched_resource_summaries):
        self.resource_id = None
        resource_summary = Mock(logical_resource_id=self.resource_id)
        patched_resource_summaries.return_value = {self.resource_id: resource_summary}
        with self._get_remote_invoke_context() as remote_invoke_context:
            self.assertEqual(remote_invoke_context._resource_summary, resource_summary)

    def test_only_resource_id_unsupported_service_arn_should_fail(self):
        self.stack_name = None
        self.resource_id = "arn:aws:unsupported-service:region:account:resource_type:resource_id"
        with self.assertRaises(UnsupportedServiceForRemoteInvoke):
            with self._get_remote_invoke_context():
                pass

    def test_only_resource_id_supported_service_arn_should_be_valid(self):
        self.stack_name = None
        service = "lambda"
        self.resource_id = f"arn:aws:{service}:region:account:resource_type:{self.resource_id}"
        with self._get_remote_invoke_context() as remote_invoke_context:
            self.assertEqual(
                remote_invoke_context._resource_summary,
                CloudFormationResourceSummary(
                    SUPPORTED_SERVICES.get("%s" % service), "%s" % self.resource_id, "%s" % self.resource_id
                ),
            )

    @patch("samcli.commands.remote.remote_invoke_context.get_resource_summary_from_physical_id")
    def test_only_resource_id_as_invalid_physical_id_should_fail(self, patched_resource_summary_from_physical_id):
        self.stack_name = None
        patched_resource_summary_from_physical_id.return_value = None
        with self.assertRaises(AmbiguousResourceForRemoteInvoke):
            with self._get_remote_invoke_context():
                pass

    @patch("samcli.commands.remote.remote_invoke_context.get_resource_summary")
    def test_if_no_resource_found_with_given_stack_and_resource_id_should_fail(self, patched_get_resource_summary):
        patched_get_resource_summary.return_value = None
        with self.assertRaises(AmbiguousResourceForRemoteInvoke):
            with self._get_remote_invoke_context() as remote_invoke_context:
                remote_invoke_context.run(Mock())

    @patch("samcli.commands.remote.remote_invoke_context.get_resource_summary_from_physical_id")
    def test_only_resource_id_as_valid_physical_id_should_be_valid(self, patched_resource_summary_from_physical_id):
        self.stack_name = None
        resource_summary = Mock()
        patched_resource_summary_from_physical_id.return_value = resource_summary
        with self._get_remote_invoke_context() as remote_invoke_context:
            self.assertEqual(remote_invoke_context._resource_summary, resource_summary)

    @patch("samcli.commands.remote.remote_invoke_context.get_resource_summary")
    def test_running_without_resource_summary_should_raise_exception(self, patched_get_resource_summary):
        patched_get_resource_summary.return_value = None
        with self._get_remote_invoke_context() as remote_invoke_context:
            with self.assertRaises(AmbiguousResourceForRemoteInvoke):
                remote_invoke_context.run(Mock())

    @patch("samcli.commands.remote.remote_invoke_context.get_resource_summary")
    def test_running_with_unsupported_resource_should_raise_exception(self, patched_get_resource_summary):
        patched_get_resource_summary.return_value = Mock(resource_type="UnSupportedResource")
        with self._get_remote_invoke_context() as remote_invoke_context:
            with self.assertRaises(NoExecutorFoundForRemoteInvoke):
                remote_invoke_context.run(Mock())

    @patch("samcli.commands.remote.remote_invoke_context.RemoteInvokeExecutorFactory")
    @patch("samcli.commands.remote.remote_invoke_context.get_resource_summary")
    def test_running_should_execute_remote_invoke_executor_instance(
        self, patched_get_resource_summary, patched_remote_invoke_executor_factory
    ):
        mocked_remote_invoke_executor_factory = Mock()
        patched_remote_invoke_executor_factory.return_value = mocked_remote_invoke_executor_factory
        mocked_remote_invoke_executor = Mock()
        mocked_output = Mock()
        mocked_remote_invoke_executor.execute.return_value = mocked_output
        mocked_remote_invoke_executor_factory.create_remote_invoke_executor.return_value = mocked_remote_invoke_executor

        given_input = Mock()
        with self._get_remote_invoke_context() as remote_invoke_context:
            remote_invoke_result = remote_invoke_context.run(given_input)

            mocked_remote_invoke_executor_factory.create_remote_invoke_executor.assert_called_once()
            mocked_remote_invoke_executor.execute.assert_called_with(given_input)
            self.assertEqual(remote_invoke_result, mocked_output)
