from unittest import TestCase
from unittest.mock import ANY, MagicMock, patch, Mock

from parameterized import parameterized_class

from samcli.lib.sync.flows.function_sync_flow import FunctionSyncFlow


@parameterized_class(
    ("build_artifacts"),
    [
        (None,),
        (Mock(),),
    ],
)
class TestFunctionSyncFlow(TestCase):
    build_artifacts = None

    def create_function_sync_flow(self):
        sync_flow = FunctionSyncFlow(
            "Function1",
            build_context=MagicMock(),
            deploy_context=MagicMock(),
            sync_context=MagicMock(),
            physical_id_mapping={},
            stacks=[MagicMock()],
            application_build_result=self.build_artifacts,
        )
        sync_flow.gather_resources = MagicMock()
        sync_flow.compare_remote = MagicMock()
        sync_flow.sync = MagicMock()
        sync_flow._get_resource_api_calls = MagicMock()
        return sync_flow

    @patch("samcli.lib.sync.sync_flow.get_boto_client_provider_from_session_with_config")
    @patch("samcli.lib.sync.sync_flow.Session")
    @patch.multiple(FunctionSyncFlow, __abstractmethods__=set())
    def test_sets_up_clients(self, session_mock, client_provider_mock):
        sync_flow = self.create_function_sync_flow()
        sync_flow.set_up()
        client_provider_mock.return_value.assert_called_once_with("lambda")
        sync_flow._lambda_client.get_waiter.assert_called_once_with("function_updated")

    @patch("samcli.lib.sync.flows.function_sync_flow.AliasVersionSyncFlow")
    @patch("samcli.lib.sync.sync_flow.Session")
    @patch.multiple(FunctionSyncFlow, __abstractmethods__=set())
    def test_gather_dependencies(self, session_mock, alias_version_mock):
        sync_flow = self.create_function_sync_flow()
        sync_flow.get_physical_id = lambda x: "PhysicalFunction1"
        sync_flow._get_resource = lambda x: MagicMock()

        sync_flow.set_up()
        result = sync_flow.gather_dependencies()

        sync_flow._lambda_waiter.wait.assert_called_once_with(FunctionName="PhysicalFunction1", WaiterConfig=ANY)
        self.assertEqual(result, [alias_version_mock.return_value])

    @patch.multiple(FunctionSyncFlow, __abstractmethods__=set())
    def test_equality_keys(self):
        sync_flow = self.create_function_sync_flow()
        self.assertEqual(sync_flow._equality_keys(), "Function1")
