from unittest import TestCase
from unittest.mock import MagicMock, mock_open, patch

from samcli.lib.sync.flows.rest_api_sync_flow import RestApiSyncFlow
from samcli.lib.providers.exceptions import MissingLocalDefinition


class TestRestApiSyncFlow(TestCase):
    def create_sync_flow(self):
        sync_flow = RestApiSyncFlow(
            "Api1",
            build_context=MagicMock(),
            deploy_context=MagicMock(),
            physical_id_mapping={},
            stacks=[MagicMock()],
        )
        return sync_flow

    @patch("samcli.lib.sync.sync_flow.get_boto_client_provider_from_session_with_config")
    @patch("samcli.lib.sync.sync_flow.SyncFlow.get_physical_id")
    @patch("samcli.lib.sync.sync_flow.Session")
    def test_set_up(self, session_mock, physical_id_mock, client_provider_mock):
        physical_id_mock.return_value = "PhysicalId"
        sync_flow = self.create_sync_flow()
        sync_flow.set_up()
        client_provider_mock.return_value.assert_any_call("apigateway")
        self.assertEqual(sync_flow._api_physical_id, "PhysicalId")

    @patch("samcli.lib.sync.sync_flow.Session")
    @patch("samcli.lib.sync.flows.rest_api_sync_flow.RestApiSyncFlow._update_api")
    @patch("samcli.lib.sync.flows.rest_api_sync_flow.RestApiSyncFlow._create_deployment")
    @patch("samcli.lib.sync.flows.rest_api_sync_flow.RestApiSyncFlow._collect_stages")
    @patch("samcli.lib.sync.flows.rest_api_sync_flow.RestApiSyncFlow._update_stages")
    @patch("samcli.lib.sync.flows.rest_api_sync_flow.RestApiSyncFlow._delete_deployments")
    def test_sync_direct(
        self, delete_mock, update_stage_mock, collect_mock, create_mock, update_api_mock, session_mock
    ):
        sync_flow = self.create_sync_flow()

        sync_flow.get_physical_id = MagicMock()
        sync_flow.get_physical_id.return_value = "PhysicalApi1"

        sync_flow._get_definition_file = MagicMock()
        sync_flow._get_definition_file.return_value = "file.yaml"

        sync_flow.set_up()
        with patch("builtins.open", mock_open(read_data='{"key": "value"}'.encode("utf-8"))) as mock_file:
            sync_flow.gather_resources()

        sync_flow.sync()
        sync_flow._update_api.assert_called_once()
        sync_flow._create_deployment.assert_called_once()
        sync_flow._collect_stages.assert_called_once()

    @patch("samcli.lib.sync.sync_flow.Session")
    def tetst_update_api(self, session_mock):
        sync_flow = self.create_sync_flow()

        sync_flow.get_physical_id = MagicMock()
        sync_flow.get_physical_id.return_value = "PhysicalApi1"

        sync_flow._get_definition_file = MagicMock()
        sync_flow._get_definition_file.return_value = "file.yaml"

        sync_flow.set_up()
        with patch("builtins.open", mock_open(read_data='{"key": "value"}'.encode("utf-8"))) as mock_file:
            sync_flow.gather_resources()

        sync_flow._api_client.put_rest_api.return_value = {"Response": "success"}

        sync_flow._update_api()
        sync_flow._api_client.put_rest_api.assert_called_once_with(
            restApiId="PhysicalApi1", mode="overwrite", body='{"key": "value"}'.encode("utf-8")
        )

    @patch("samcli.lib.sync.flows.generic_api_sync_flow.get_resource_by_id")
    def test_get_definition_file(self, get_resource_mock):
        sync_flow = self.create_sync_flow()

        get_resource_mock.return_value = {"Properties": {"DefinitionUri": "test_uri"}}
        result_uri = sync_flow._get_definition_file("test")

        self.assertEqual(result_uri, "test_uri")

        get_resource_mock.return_value = {"Properties": {}}
        result_uri = sync_flow._get_definition_file("test")

        self.assertEqual(result_uri, None)

    def test_process_definition_file(self):
        sync_flow = self.create_sync_flow()
        sync_flow._definition_uri = "path"
        with patch("builtins.open", mock_open(read_data='{"key": "value"}'.encode("utf-8"))) as mock_file:
            data = sync_flow._process_definition_file()
            self.assertEqual(data, '{"key": "value"}'.encode("utf-8"))

    @patch("samcli.lib.sync.sync_flow.Session")
    def test_failed_gather_resources(self, session_mock):
        sync_flow = self.create_sync_flow()

        sync_flow.get_physical_id = MagicMock()
        sync_flow.get_physical_id.return_value = "PhysicalApi1"

        sync_flow._get_definition_file = MagicMock()
        sync_flow._get_definition_file.return_value = "file.yaml"

        sync_flow.set_up()
        sync_flow._definition_uri = None

        with patch("builtins.open", mock_open(read_data='{"key": "value"}'.encode("utf-8"))) as mock_file:
            with self.assertRaises(MissingLocalDefinition):
                sync_flow.sync()

    def test_compare_remote(self):
        sync_flow = self.create_sync_flow()
        self.assertFalse(sync_flow.compare_remote())

    def test_gather_dependencies(self):
        sync_flow = self.create_sync_flow()
        self.assertEqual(sync_flow.gather_dependencies(), [])

    def test_equality_keys(self):
        sync_flow = self.create_sync_flow()
        self.assertEqual(sync_flow._equality_keys(), sync_flow._api_identifier)

    def test_get_resource_api_calls(self):
        sync_flow = self.create_sync_flow()
        self.assertEqual(sync_flow._get_resource_api_calls(), [])
