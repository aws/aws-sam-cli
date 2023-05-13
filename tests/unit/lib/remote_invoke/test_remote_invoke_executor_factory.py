from unittest import TestCase
from unittest.mock import patch, Mock

from samcli.lib.remote_invoke.remote_invoke_executor_factory import RemoteInvokeExecutorFactory


class TestRemoteInvokeExecutorFactory(TestCase):
    def setUp(self) -> None:
        self.boto_client_provider_mock = Mock()
        self.test_executor_factory = RemoteInvokeExecutorFactory(self.boto_client_provider_mock)

    @patch(
        "samcli.lib.remote_invoke.remote_invoke_executor_factory.RemoteInvokeExecutorFactory.REMOTE_INVOKE_EXECUTOR_MAPPING"
    )
    def test_create_test_executor(self, patched_executor_mapping):
        given_executor_creator_method = Mock()
        patched_executor_mapping.get.return_value = given_executor_creator_method

        given_executor = Mock()
        given_executor_creator_method.return_value = given_executor

        given_cfn_resource_summary = Mock()
        executor = self.test_executor_factory.create_remote_invoke_executor(given_cfn_resource_summary)

        patched_executor_mapping.get.assert_called_with(given_cfn_resource_summary.resource_type)
        given_executor_creator_method.assert_called_with(self.test_executor_factory, given_cfn_resource_summary)
        self.assertEqual(executor, given_executor)

    def test_failed_create_test_executor(self):
        given_cfn_resource_summary = Mock()
        executor = self.test_executor_factory.create_remote_invoke_executor(given_cfn_resource_summary)
        self.assertIsNone(executor)
