from pathlib import Path
from samcli.lib.providers.provider import ResourceIdentifier, Stack
from unittest import TestCase
from unittest.mock import MagicMock, patch, Mock

from samcli.lib.sync.sync_flow import SyncFlow, ResourceAPICall, ApiCallTypes, get_definition_path
from parameterized import parameterized


class TestSyncFlow(TestCase):
    def create_sync_flow(self):
        sync_flow = SyncFlow(
            build_context=MagicMock(),
            deploy_context=MagicMock(),
            physical_id_mapping={},
            log_name="log-name",
            stacks=[MagicMock()],
        )
        sync_flow.gather_resources = MagicMock()
        sync_flow.compare_remote = MagicMock()
        sync_flow.sync = MagicMock()
        sync_flow.gather_dependencies = MagicMock()
        sync_flow._get_resource_api_calls = MagicMock()
        return sync_flow

    @patch("samcli.lib.sync.sync_flow.Session")
    @patch.multiple(SyncFlow, __abstractmethods__=set())
    def test_execute_all_steps(self, session_mock):
        sync_flow = self.create_sync_flow()
        sync_flow.compare_remote.return_value = False
        sync_flow.gather_dependencies.return_value = ["A"]
        result = sync_flow.execute()

        sync_flow.gather_resources.assert_called_once()
        sync_flow.compare_remote.assert_called_once()
        sync_flow.sync.assert_called_once()
        sync_flow.gather_dependencies.assert_called_once()
        self.assertEqual(result, ["A"])

    @patch("samcli.lib.sync.sync_flow.Session")
    @patch.multiple(SyncFlow, __abstractmethods__=set())
    def test_execute_skip_after_compare(self, session_mock):
        sync_flow = self.create_sync_flow()
        sync_flow.compare_remote.return_value = True
        sync_flow.gather_dependencies.return_value = ["A"]
        result = sync_flow.execute()

        sync_flow.gather_resources.assert_called_once()
        sync_flow.compare_remote.assert_called_once()
        sync_flow.sync.assert_not_called()
        sync_flow.gather_dependencies.assert_not_called()
        self.assertEqual(result, [])

    @patch("samcli.lib.sync.sync_flow.Session")
    @patch.multiple(SyncFlow, __abstractmethods__=set())
    def test_set_up(self, session_mock):
        sync_flow = self.create_sync_flow()
        sync_flow.set_up()
        session_mock.assert_called_once()
        self.assertIsNotNone(sync_flow._session)

    @patch("samcli.lib.sync.sync_flow.get_boto_client_provider_from_session_with_config")
    @patch.multiple(SyncFlow, __abstractmethods__=set())
    def test_boto_client(self, patched_get_client):
        client_name = "lambda"
        given_client_generator = Mock()
        patched_get_client.return_value = given_client_generator
        given_client = Mock()
        given_client_generator.return_value = given_client

        sync_flow = self.create_sync_flow()
        with patch.object(sync_flow, "_session") as patched_session:
            client = sync_flow._boto_client(client_name)

            patched_get_client.assert_called_with(patched_session)
            given_client_generator.assert_called_with(client_name)
            self.assertEqual(client, given_client)

    @patch("samcli.lib.sync.sync_flow.Session")
    @patch.multiple(SyncFlow, __abstractmethods__=set())
    def test_set_locks_with_distributor(self, session_mock):
        sync_flow = self.create_sync_flow()
        distributor = MagicMock()
        locks = {"A": 1, "B": 2}
        distributor.get_locks.return_value = locks
        sync_flow.set_locks_with_distributor(distributor)
        self.assertEqual(locks, sync_flow._locks)

    @parameterized.expand([({"A": 1, "B": 2}, True), ({"A": 1}, True), ({}, False)])
    @patch.multiple(SyncFlow, __abstractmethods__=set())
    def test_has_locks(self, locks, expected_result):
        sync_flow = self.create_sync_flow()
        distributor = MagicMock()
        distributor.get_locks.return_value = locks
        sync_flow.set_locks_with_distributor(distributor)
        has_locks = sync_flow.has_locks()
        self.assertEqual(has_locks, expected_result)

    @patch.multiple(SyncFlow, __abstractmethods__=set())
    def test_get_lock_keys(self):
        sync_flow = self.create_sync_flow()
        sync_flow._get_resource_api_calls.return_value = [
            ResourceAPICall("A", [ApiCallTypes.BUILD]),
            ResourceAPICall("B", [ApiCallTypes.UPDATE_FUNCTION_CONFIGURATION]),
        ]
        result = sync_flow.get_lock_keys()
        self.assertEqual(sorted(result), sorted(["A_Build", "B_UpdateFunctionConfiguration"]))

    @patch("samcli.lib.sync.sync_flow.LockChain")
    @patch("samcli.lib.sync.sync_flow.Session")
    @patch.multiple(SyncFlow, __abstractmethods__=set())
    def test_get_lock_chain(self, session_mock, lock_chain_mock):
        sync_flow = self.create_sync_flow()
        locks = {"A": 1, "B": 2}
        sync_flow._locks = locks
        result = sync_flow._get_lock_chain()
        lock_chain_mock.assert_called_once_with(locks)

    @patch.multiple(SyncFlow, __abstractmethods__=set())
    def test_log_prefix(self):
        sync_flow = self.create_sync_flow()
        sync_flow._log_name = "A"
        self.assertEqual(sync_flow.log_prefix, "SyncFlow [A]: ")

    @patch.multiple(SyncFlow, __abstractmethods__=set())
    def test_eq_true(self):
        sync_flow_1 = self.create_sync_flow()
        sync_flow_1._equality_keys = MagicMock()
        sync_flow_1._equality_keys.return_value = "A"
        sync_flow_2 = self.create_sync_flow()
        sync_flow_2._equality_keys = MagicMock()
        sync_flow_2._equality_keys.return_value = "A"
        self.assertTrue(sync_flow_1 == sync_flow_2)

    @patch.multiple(SyncFlow, __abstractmethods__=set())
    def test_eq_false(self):
        sync_flow_1 = self.create_sync_flow()
        sync_flow_1._equality_keys = MagicMock()
        sync_flow_1._equality_keys.return_value = "A"
        sync_flow_2 = self.create_sync_flow()
        sync_flow_2._equality_keys = MagicMock()
        sync_flow_2._equality_keys.return_value = "B"
        self.assertFalse(sync_flow_1 == sync_flow_2)

    @patch.multiple(SyncFlow, __abstractmethods__=set())
    def test_hash(self):
        sync_flow = self.create_sync_flow()
        sync_flow._equality_keys = MagicMock()
        sync_flow._equality_keys.return_value = "A"
        self.assertEqual(hash(sync_flow), hash((type(sync_flow), "A")))

    @patch("samcli.lib.sync.sync_flow.Stack.get_stack_by_full_path")
    def test_get_definition_path(self, get_stack_mock):
        resource = {"Properties": {"DefinitionUri": "test_uri"}}
        get_stack_mock.return_value = Stack("parent_path", "stack_name", "location/template.yaml", None, {})

        definition_path = get_definition_path(resource, "identifier", False, "base_dir", [])
        self.assertEqual(definition_path, Path("location").joinpath("test_uri"))

        resource = {"Properties": {"DefinitionUri": ""}}
        definition_path = get_definition_path(resource, "identifier", False, "base_dir", [])
        self.assertEqual(definition_path, None)

    def test_get_definition_file_with_base_dir(self):
        resource = {"Properties": {"DefinitionUri": "test_uri"}}

        definition_path = get_definition_path(resource, "identifier", True, "base_dir", [])
        self.assertEqual(definition_path, Path("base_dir").joinpath("test_uri"))
