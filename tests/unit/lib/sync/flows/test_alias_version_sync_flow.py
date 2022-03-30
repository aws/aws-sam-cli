import os
import hashlib

from samcli.lib.sync.sync_flow import SyncFlow
from unittest import TestCase
from unittest.mock import ANY, MagicMock, call, mock_open, patch

from samcli.lib.sync.flows.alias_version_sync_flow import AliasVersionSyncFlow


class TestAliasVersionSyncFlow(TestCase):
    def create_sync_flow(self):
        sync_flow = AliasVersionSyncFlow(
            "Function1",
            "Alias1",
            build_context=MagicMock(),
            deploy_context=MagicMock(),
            physical_id_mapping={},
            stacks=[MagicMock()],
        )
        return sync_flow

    @patch("samcli.lib.sync.sync_flow.get_boto_client_provider_from_session_with_config")
    @patch("samcli.lib.sync.sync_flow.Session")
    def test_set_up(self, session_mock, client_provider_mock):
        sync_flow = self.create_sync_flow()
        sync_flow.set_up()
        client_provider_mock.return_value.assert_any_call("lambda")

    @patch("samcli.lib.sync.sync_flow.Session")
    def test_sync_direct(self, session_mock):
        sync_flow = self.create_sync_flow()

        sync_flow.get_physical_id = MagicMock()
        sync_flow.get_physical_id.return_value = "PhysicalFunction1"

        sync_flow.set_up()

        sync_flow._lambda_client.publish_version.return_value = {"Version": "2"}

        sync_flow.sync()

        sync_flow._lambda_client.publish_version.assert_called_once_with(FunctionName="PhysicalFunction1")
        sync_flow._lambda_client.update_alias.assert_called_once_with(
            FunctionName="PhysicalFunction1", Name="Alias1", FunctionVersion="2"
        )

    def test_equality_keys(self):
        sync_flow = self.create_sync_flow()
        self.assertEqual(sync_flow._equality_keys(), ("Function1", "Alias1"))

    def test_gather_dependencies(self):
        sync_flow = self.create_sync_flow()
        self.assertEqual(sync_flow.gather_dependencies(), [])

    def test_get_resource_api_calls(self):
        sync_flow = self.create_sync_flow()
        self.assertEqual(sync_flow._get_resource_api_calls(), [])

    def test_compare_remote(self):
        sync_flow = self.create_sync_flow()
        self.assertFalse(sync_flow.compare_remote())
