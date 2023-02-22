from unittest import TestCase
from unittest.mock import MagicMock, mock_open, patch, call
from pathlib import Path

from botocore.exceptions import ClientError

from samcli.lib.utils.colors import Colored
from samcli.lib.sync.flows.rest_api_sync_flow import RestApiSyncFlow
from samcli.lib.providers.exceptions import MissingLocalDefinition
from samcli.lib.providers.provider import ResourceIdentifier, Stack
from samcli.lib.utils.hash import str_checksum


class TestRestApiSyncFlow(TestCase):
    def create_sync_flow(self):
        sync_flow = RestApiSyncFlow(
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
        sync_flow.get_physical_id = MagicMock()
        sync_flow.get_physical_id.return_value = "PhysicalId"
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

        create_mock.return_value = "abc"
        collect_mock.return_value = {"beta", "prod", "Stage"}
        update_stage_mock.return_value = {"def"}

        sync_flow.sync()
        sync_flow._update_api.assert_called_once()
        sync_flow._create_deployment.assert_called_once()
        sync_flow._collect_stages.assert_called_once()
        sync_flow._update_stages.assert_called_once_with({"beta", "prod", "Stage"}, "abc")
        sync_flow._delete_deployments.assert_called_once_with({"def"})

    @patch("samcli.lib.sync.sync_flow.Session")
    def test_update_api(self, session_mock):
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

    @patch("samcli.lib.sync.sync_flow.Session")
    def test_create_deployment(self, session_mock):
        sync_flow = self.create_sync_flow()

        sync_flow.get_physical_id = MagicMock()
        sync_flow.get_physical_id.return_value = "PhysicalApi1"

        sync_flow._get_definition_file = MagicMock()
        sync_flow._get_definition_file.return_value = "file.yaml"

        sync_flow.set_up()
        with patch("builtins.open", mock_open(read_data='{"key": "value"}'.encode("utf-8"))) as mock_file:
            sync_flow.gather_resources()

        sync_flow._api_client.create_deployment.return_value = {"id": "abc"}

        deployment_id = sync_flow._create_deployment()
        sync_flow._api_client.create_deployment.assert_called_once_with(
            restApiId="PhysicalApi1", description="Created by SAM Sync"
        )
        self.assertEqual(deployment_id, "abc")

    @patch("samcli.lib.sync.flows.rest_api_sync_flow.get_resource_by_id")
    @patch("samcli.lib.sync.flows.rest_api_sync_flow.get_resource_ids_by_type")
    @patch("samcli.lib.sync.sync_flow.Session")
    def test_collect_stages_sam_api(self, session_mock, get_id_mock, get_resource_mock):
        sync_flow = self.create_sync_flow()

        sync_flow.get_physical_id = MagicMock()
        sync_flow.get_physical_id.return_value = "PhysicalApi1"

        sync_flow._get_definition_file = MagicMock()
        sync_flow._get_definition_file.return_value = "file.yaml"

        sync_flow.set_up()
        with patch("builtins.open", mock_open(read_data='{"key": "value"}'.encode("utf-8"))) as mock_file:
            sync_flow.gather_resources()

        get_id_mock.return_value = [ResourceIdentifier("Resource1")]
        # Integrating stage resource properties and api resource properties into one dict for simplicity
        get_resource_mock.return_value = {
            "Type": "AWS::Serverless::Api",
            "Properties": {
                "StageName": "beta",
                "RestApiId": "Api1",
            },
        }

        sync_flow._api_client.get_stages.return_value = {"item": [{"stageName": "Stage"}]}

        stages = sync_flow._collect_stages()
        sync_flow._api_client.get_stages.assert_called_once_with(restApiId="PhysicalApi1")
        self.assertEqual(stages, {"beta", "Stage"})

    @patch("samcli.lib.sync.flows.rest_api_sync_flow.get_resource_by_id")
    @patch("samcli.lib.sync.flows.rest_api_sync_flow.get_resource_ids_by_type")
    @patch("samcli.lib.sync.sync_flow.Session")
    def test_collect_stages_apigateway_api(self, session_mock, get_id_mock, get_resource_mock):
        sync_flow = self.create_sync_flow()

        sync_flow.get_physical_id = MagicMock()
        sync_flow.get_physical_id.return_value = "PhysicalApi1"

        sync_flow._get_definition_file = MagicMock()
        sync_flow._get_definition_file.return_value = "file.yaml"

        sync_flow.set_up()
        with patch("builtins.open", mock_open(read_data='{"key": "value"}'.encode("utf-8"))) as mock_file:
            sync_flow.gather_resources()

        get_id_mock.return_value = [ResourceIdentifier("Resource1")]
        # Integrating stage resource properties and api resource properties into one dict for simplicity
        get_resource_mock.return_value = {
            "Type": "AWS::ApiGateway::RestApi",
            "Properties": {"StageName": "beta", "RestApiId": "Api1", "DeploymentId": "Resource1"},
        }

        stages = sync_flow._collect_stages()
        sync_flow._api_client.get_stages.assert_not_called()
        self.assertEqual(stages, {"beta"})

    @patch("samcli.lib.sync.sync_flow.Session")
    def test_update_stage(self, session_mock):
        sync_flow = self.create_sync_flow()

        sync_flow.get_physical_id = MagicMock()
        sync_flow.get_physical_id.return_value = "PhysicalApi1"

        sync_flow._get_definition_file = MagicMock()
        sync_flow._get_definition_file.return_value = "file.yaml"

        sync_flow.set_up()
        with patch("builtins.open", mock_open(read_data='{"key": "value"}'.encode("utf-8"))) as mock_file:
            sync_flow.gather_resources()

        sync_flow._api_client.get_stage.return_value = {"deploymentId": "abc"}

        # Using list for set inputs to preserve iteration order
        stages = ["Stage", "beta"]
        deployment_id = "def"
        prev_ids = sync_flow._update_stages(stages, deployment_id)

        sync_flow._api_client.get_stage.assert_has_calls(
            [call(restApiId="PhysicalApi1", stageName="Stage"), call(restApiId="PhysicalApi1", stageName="beta")]
        )
        sync_flow._api_client.update_stage.assert_has_calls(
            [
                call(
                    restApiId="PhysicalApi1",
                    stageName="Stage",
                    patchOperations=[{"op": "replace", "path": "/deploymentId", "value": deployment_id}],
                ),
                call(
                    restApiId="PhysicalApi1",
                    stageName="beta",
                    patchOperations=[{"op": "replace", "path": "/deploymentId", "value": deployment_id}],
                ),
            ]
        )
        sync_flow._api_client.flush_stage_cache.assert_has_calls(
            [call(restApiId="PhysicalApi1", stageName="Stage"), call(restApiId="PhysicalApi1", stageName="beta")]
        )
        sync_flow._api_client.flush_stage_authorizers_cache.assert_has_calls(
            [call(restApiId="PhysicalApi1", stageName="Stage"), call(restApiId="PhysicalApi1", stageName="beta")]
        )

        self.assertEqual(prev_ids, {"abc"})

    @patch("samcli.lib.sync.sync_flow.Session")
    def test_delete_deployment(self, session_mock):
        sync_flow = self.create_sync_flow()

        sync_flow.get_physical_id = MagicMock()
        sync_flow.get_physical_id.return_value = "PhysicalApi1"

        sync_flow._get_definition_file = MagicMock()
        sync_flow._get_definition_file.return_value = "file.yaml"

        sync_flow.set_up()
        with patch("builtins.open", mock_open(read_data='{"key": "value"}'.encode("utf-8"))) as mock_file:
            sync_flow.gather_resources()

        # Using list for set inputs to preserve iteration order
        prev_dep_ids = ["abc", "def"]
        sync_flow._delete_deployments(prev_dep_ids)

        sync_flow._api_client.delete_deployment.assert_has_calls(
            [call(restApiId="PhysicalApi1", deploymentId="abc"), call(restApiId="PhysicalApi1", deploymentId="def")]
        )

    @patch("samcli.lib.sync.sync_flow.Session")
    def test_delete_deployment_failure(self, session_mock):
        sync_flow = self.create_sync_flow()

        sync_flow.get_physical_id = MagicMock()
        sync_flow.get_physical_id.return_value = "PhysicalApi1"

        sync_flow._get_definition_file = MagicMock()
        sync_flow._get_definition_file.return_value = "file.yaml"

        sync_flow.set_up()
        with patch("builtins.open", mock_open(read_data='{"key": "value"}'.encode("utf-8"))) as mock_file:
            sync_flow.gather_resources()

        sync_flow._api_client.delete_deployment.side_effect = ClientError({}, "DeleteDeployment")

        prev_dep_ids = {"abc"}

        with patch("samcli.lib.sync.flows.rest_api_sync_flow.LOG.warning") as warning_mock:
            sync_flow._delete_deployments(prev_dep_ids)
            warning_mock.assert_called_once_with(
                Colored().yellow(
                    "Delete deployment for %s failed, it may be due to the it being used by another stage. \
please check the console to see if you have other stages that needs to be updated."
                ),
                "abc",
            )

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
