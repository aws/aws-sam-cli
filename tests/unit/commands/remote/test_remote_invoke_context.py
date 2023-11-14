from unittest import TestCase
from unittest.mock import Mock, patch
from parameterized import parameterized
from uuid import uuid4

from samcli.commands.remote.exceptions import (
    InvalidRemoteInvokeParameters,
    AmbiguousResourceForRemoteInvoke,
    NoResourceFoundForRemoteInvoke,
    UnsupportedServiceForRemoteInvoke,
    ResourceNotSupportedForRemoteInvoke,
    InvalidStackNameProvidedForRemoteInvoke,
)
from samcli.commands.remote.remote_invoke_context import (
    RemoteInvokeContext,
    SUPPORTED_SERVICES,
    RESOURCES_PRIORITY_ORDER,
)
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

    def test_supported_services_and_priority_order_services_are_same(self):
        self.assertEqual(set(SUPPORTED_SERVICES.values()), set(RESOURCES_PRIORITY_ORDER))

    @parameterized.expand(
        [
            (
                {
                    "resource1": Mock(resource_type=SUPPORTED_SERVICES["lambda"]),
                    "resource2": Mock(resource_type=SUPPORTED_SERVICES["lambda"]),
                    "resource3": Mock(resource_type=SUPPORTED_SERVICES["states"]),
                    "resource4": Mock(resource_type=SUPPORTED_SERVICES["sqs"]),
                    "resource5": Mock(resource_type=SUPPORTED_SERVICES["kinesis"]),
                },
            ),
            (
                {
                    "resource1": Mock(resource_type=SUPPORTED_SERVICES["states"]),
                    "resource2": Mock(resource_type=SUPPORTED_SERVICES["states"]),
                    "resource3": Mock(resource_type=SUPPORTED_SERVICES["sqs"]),
                    "resource4": Mock(resource_type=SUPPORTED_SERVICES["kinesis"]),
                },
            ),
            (
                {
                    "resource1": Mock(resource_type=SUPPORTED_SERVICES["sqs"]),
                    "resource2": Mock(resource_type=SUPPORTED_SERVICES["sqs"]),
                    "resource3": Mock(resource_type=SUPPORTED_SERVICES["kinesis"]),
                },
            ),
            (
                {
                    "resource1": Mock(resource_type=SUPPORTED_SERVICES["kinesis"]),
                    "resource2": Mock(resource_type=SUPPORTED_SERVICES["kinesis"]),
                },
            ),
        ]
    )
    @patch("samcli.commands.remote.remote_invoke_context.get_resource_summaries")
    def test_only_stack_name_with_multiple_same_resource_type_should_fail(
        self, mock_resource_summaries, patched_resource_summaries
    ):
        self.resource_id = None
        patched_resource_summaries.return_value = mock_resource_summaries
        with self.assertRaises(AmbiguousResourceForRemoteInvoke):
            with self._get_remote_invoke_context():
                pass

    @patch("samcli.commands.remote.remote_invoke_context.get_resource_summaries")
    def test_only_stack_name_with_single_resource_should_be_valid(self, patched_resource_summaries):
        self.resource_id = None
        resource_summary = Mock(logical_resource_id="mock-resource-id")
        patched_resource_summaries.return_value = {self.resource_id: resource_summary}
        with self._get_remote_invoke_context() as remote_invoke_context:
            self.assertEqual(remote_invoke_context._resource_summary, resource_summary)

    @parameterized.expand(
        [
            (
                {
                    "resource2": Mock(resource_type=SUPPORTED_SERVICES["states"], logical_resource_id="resource2"),
                    "resource1": Mock(resource_type=SUPPORTED_SERVICES["sqs"], logical_resource_id="resource1"),
                    "resource3": Mock(resource_type=SUPPORTED_SERVICES["lambda"], logical_resource_id="resource3"),
                    "resource4": Mock(resource_type=SUPPORTED_SERVICES["kinesis"], logical_resource_id="resource4"),
                },
                "resource3",
            ),
            (
                {
                    "resource1": Mock(resource_type=SUPPORTED_SERVICES["states"], logical_resource_id="resource1"),
                    "resource2": Mock(resource_type=SUPPORTED_SERVICES["sqs"], logical_resource_id="resource2"),
                    "resource3": Mock(resource_type=SUPPORTED_SERVICES["kinesis"], logical_resource_id="resource3"),
                    "resource4": Mock(resource_type=SUPPORTED_SERVICES["sqs"], logical_resource_id="resource4"),
                },
                "resource1",
            ),
            (
                {
                    "resource1": Mock(resource_type=SUPPORTED_SERVICES["sqs"], logical_resource_id="resource1"),
                    "resource2": Mock(resource_type=SUPPORTED_SERVICES["kinesis"], logical_resource_id="resource2"),
                },
                "resource1",
            ),
            (
                {
                    "resource1": Mock(resource_type=SUPPORTED_SERVICES["kinesis"], logical_resource_id="resource1"),
                },
                "resource1",
            ),
        ]
    )
    @patch("samcli.commands.remote.remote_invoke_context.get_resource_summaries")
    def test_only_stack_name_service_priority_invoke(
        self, mock_resource_summaries, expected_logical_id, patched_resource_summaries
    ):
        self.resource_id = None
        patched_resource_summaries.return_value = mock_resource_summaries
        with self._get_remote_invoke_context() as remote_invoke_context:
            self.assertEqual(remote_invoke_context._resource_summary.logical_resource_id, expected_logical_id)

    def test_only_resource_id_unsupported_service_arn_should_fail(self):
        self.stack_name = None
        self.resource_id = "arn:aws:unsupported-service:region:account:resource_type:resource_id"
        with self.assertRaises(UnsupportedServiceForRemoteInvoke):
            with self._get_remote_invoke_context():
                pass

    @parameterized.expand(
        [
            ("lambda"),
            ("states"),
        ]
    )
    def test_only_resource_id_supported_service_arn_should_be_valid(self, service):
        self.stack_name = None
        self.resource_id = f"arn:aws:{service}:region:account:resource_type:{self.resource_id}"
        with self._get_remote_invoke_context() as remote_invoke_context:
            self.assertEqual(
                remote_invoke_context._resource_summary,
                CloudFormationResourceSummary(
                    SUPPORTED_SERVICES.get("%s" % service), "%s" % self.resource_id, "%s" % self.resource_id
                ),
            )

    @patch("samcli.commands.remote.remote_invoke_context.get_queue_url_from_arn")
    def test_only_resource_id_supported_service_sqs_arn_should_be_valid(self, patched_get_queue_url_from_arn):
        self.stack_name = None
        service = "sqs"
        mock_queue_url = "https://sqs.us-east-1.amazonaws.com/12345678910/{self.resource_id}"
        patched_get_queue_url_from_arn.return_value = mock_queue_url
        self.resource_id = f"arn:aws:{service}:region:account:resource_type:{self.resource_id}"
        with self._get_remote_invoke_context() as remote_invoke_context:
            self.assertEqual(
                remote_invoke_context._resource_summary,
                CloudFormationResourceSummary(
                    SUPPORTED_SERVICES.get("%s" % service), "%s" % mock_queue_url, "%s" % mock_queue_url
                ),
            )

    def test_only_resource_id_supported_service_kinesis_arn_should_be_valid(self):
        self.stack_name = None
        service = "kinesis"
        mock_stream_name = self.resource_id
        self.resource_id = f"arn:aws:{service}:region:account:resource_type:{self.resource_id}"
        with self._get_remote_invoke_context() as remote_invoke_context:
            self.assertEqual(
                remote_invoke_context._resource_summary,
                CloudFormationResourceSummary(
                    SUPPORTED_SERVICES.get("%s" % service), "%s" % mock_stream_name, "%s" % mock_stream_name
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
            with self.assertRaises(ResourceNotSupportedForRemoteInvoke):
                remote_invoke_context.run(Mock())

    @patch("samcli.commands.remote.remote_invoke_context.RemoteInvokeExecutorFactory")
    @patch("samcli.commands.remote.remote_invoke_context.get_resource_summary")
    def test_running_should_execute_remote_invoke_executor_instance(
        self, patched_get_resource_summary, patched_remote_invoke_executor_factory
    ):
        patched_get_resource_summary.return_value = Mock(resource_type=SUPPORTED_SERVICES["lambda"])
        mocked_remote_invoke_executor_factory = Mock()
        patched_remote_invoke_executor_factory.return_value = mocked_remote_invoke_executor_factory
        mocked_remote_invoke_executor = Mock()
        mocked_remote_invoke_executor_factory.create_remote_invoke_executor.return_value = mocked_remote_invoke_executor

        given_input = Mock()
        with self._get_remote_invoke_context() as remote_invoke_context:
            remote_invoke_context.run(given_input)

            mocked_remote_invoke_executor_factory.create_remote_invoke_executor.assert_called_once()
            mocked_remote_invoke_executor.execute.assert_called_with(given_input)
