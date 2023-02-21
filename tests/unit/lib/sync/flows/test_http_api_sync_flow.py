from unittest import TestCase
from unittest.mock import MagicMock, mock_open, patch
from pathlib import Path
from samcli.lib.providers.provider import Stack

from samcli.lib.sync.flows.http_api_sync_flow import HttpApiSyncFlow
from samcli.lib.providers.exceptions import MissingLocalDefinition
from samcli.lib.utils.hash import str_checksum


class TestHttpApiSyncFlow(TestCase):
    def create_sync_flow(self):
        sync_flow = HttpApiSyncFlow(
            "Api1",
            build_context=MagicMock(),
            deploy_context=MagicMock(),
            sync_context=MagicMock(),
            physical_id_mapping={},
            stacks=[MagicMock()],
        )
        return sync_flow

    @patch("samcli.lib.sync.sync_flow.get_boto_client_provider_from_session_with_config")
    @patch("samcli.lib.sync.sync_flow.Session")
    def test_set_up(self, session_mock, client_provider_mock):
        sync_flow = self.create_sync_flow()
        sync_flow.set_up()
        client_provider_mock.return_value.assert_any_call("apigatewayv2")

    @patch("samcli.lib.sync.sync_flow.Session")
    def test_sync_direct(self, session_mock):
        sync_flow = self.create_sync_flow()

        sync_flow.get_physical_id = MagicMock()
        sync_flow.get_physical_id.return_value = "PhysicalApi1"

        sync_flow._get_definition_file = MagicMock()
        sync_flow._get_definition_file.return_value = "file.yaml"

        sync_flow.set_up()
        with patch("builtins.open", mock_open(read_data='{"key": "value"}'.encode("utf-8"))) as mock_file:
            sync_flow.gather_resources()

        sync_flow._api_client.reimport_api.return_value = {"Response": "success"}

        sync_flow.sync()

        sync_flow._api_client.reimport_api.assert_called_once_with(ApiId="PhysicalApi1", Body='{"key": "value"}')

    @patch("samcli.lib.sync.flows.generic_api_sync_flow.get_resource_by_id")
    @patch("samcli.lib.sync.flows.generic_api_sync_flow.get_definition_path")
    def test_get_definition_file(self, get_path_mock, get_resource_mock):
        sync_flow = self.create_sync_flow()

        sync_flow._build_context.use_base_dir = False
        sync_flow._build_context.base_dir = "base_dir"
        get_resource_mock.return_value = {"Properties": {"DefinitionUri": "test_uri"}}
        get_path_mock.return_value = Path("base_dir").joinpath("test_uri")

        result_uri = sync_flow._get_definition_file(sync_flow._api_identifier)

        get_path_mock.assert_called_with(
            {"Properties": {"DefinitionUri": "test_uri"}},
            sync_flow._api_identifier,
            False,
            "base_dir",
            sync_flow._stacks,
        )
        self.assertEqual(result_uri, Path("base_dir").joinpath("test_uri"))

        get_resource_mock.return_value = {}
        result_uri = sync_flow._get_definition_file(sync_flow._api_identifier)

        self.assertEqual(result_uri, None)

    @patch("samcli.lib.sync.flows.generic_api_sync_flow.get_resource_by_id")
    @patch("samcli.lib.sync.flows.generic_api_sync_flow.get_definition_path")
    def test_get_definition_file_with_base_dir(self, get_path_mock, get_resource_mock):
        sync_flow = self.create_sync_flow()

        sync_flow._build_context.use_base_dir = True
        sync_flow._build_context.base_dir = "base_dir"
        get_resource_mock.return_value = {"Properties": {"DefinitionUri": "test_uri"}}
        get_path_mock.return_value = Path("base_dir").joinpath("test_uri")

        result_uri = sync_flow._get_definition_file(sync_flow._api_identifier)

        get_path_mock.assert_called_with(
            {"Properties": {"DefinitionUri": "test_uri"}},
            sync_flow._api_identifier,
            True,
            "base_dir",
            sync_flow._stacks,
        )
        self.assertEqual(result_uri, Path("base_dir").joinpath("test_uri"))

    def test_process_definition_file(self):
        sync_flow = self.create_sync_flow()
        sync_flow._definition_uri = "path"
        with patch("builtins.open", mock_open(read_data='{"key": "value"}'.encode("utf-8"))) as mock_file:
            data = sync_flow._process_definition_file()
            self.assertEqual(data, '{"key": "value"}'.encode("utf-8"))

    @patch("samcli.lib.sync.sync_flow.Session")
    def test_gather_resources_generate_local_sha(self, session_mock):
        sync_flow = self.create_sync_flow()

        sync_flow.get_physical_id = MagicMock()
        sync_flow.get_physical_id.return_value = "PhysicalId1"

        sync_flow._get_definition_file = MagicMock()
        sync_flow._get_definition_file.return_value = "file.yaml"

        sync_flow._process_definition_file = MagicMock()
        sync_flow._process_definition_file.return_value = '{"key": "value"}'.encode("utf-8")

        sync_flow.set_up()

        sync_flow.gather_resources()
        sync_flow._get_definition_file.assert_called_once_with("Api1")
        sync_flow._process_definition_file.assert_called_once()

        self.assertEqual(sync_flow._local_sha, str_checksum('{"key": "value"}'))

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
