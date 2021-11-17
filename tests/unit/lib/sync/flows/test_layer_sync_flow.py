import base64
import hashlib
from unittest import TestCase
from unittest.mock import MagicMock, Mock, patch, call, ANY, mock_open, PropertyMock

from parameterized import parameterized

from samcli.lib.sync.exceptions import MissingPhysicalResourceError, NoLayerVersionsFoundError
from samcli.lib.sync.flows.layer_sync_flow import LayerSyncFlow, FunctionLayerReferenceSync
from samcli.lib.sync.sync_flow import SyncFlow


class TestLayerSyncFlow(TestCase):
    def setUp(self):
        self.layer_identifier = "LayerA"
        self.build_context_mock = Mock()
        self.deploy_context_mock = Mock()

        self.layer_sync_flow = LayerSyncFlow(
            self.layer_identifier,
            self.build_context_mock,
            self.deploy_context_mock,
            {self.layer_identifier: "layer_version_arn"},
            [],
        )

    @patch("samcli.lib.sync.sync_flow.get_boto_client_provider_from_session_with_config")
    def test_setup(self, client_provider_mock):
        with patch.object(self.layer_sync_flow, "_session") as patched_session:
            with patch.object(SyncFlow, "set_up") as patched_super_setup:
                self.layer_sync_flow.set_up()

                patched_super_setup.assert_called_once()
                client_provider_mock.return_value.assert_called_with("lambda")

    @patch("samcli.lib.sync.sync_flow.get_boto_client_provider_from_session_with_config")
    @patch("samcli.lib.sync.flows.layer_sync_flow.get_resource_by_id")
    def test_setup_with_serverless_layer(self, get_resource_by_id_mock, client_provider_mock):
        given_layer_name_with_hashes = f"{self.layer_identifier}abcdefghij"
        self.layer_sync_flow._physical_id_mapping = {given_layer_name_with_hashes: "layer_version_arn"}
        get_resource_by_id_mock.return_value = False
        with patch.object(self.layer_sync_flow, "_session") as patched_session:
            with patch.object(SyncFlow, "set_up") as patched_super_setup:
                self.layer_sync_flow.set_up()

                patched_super_setup.assert_called_once()
                client_provider_mock.return_value.assert_called_with("lambda")

        self.assertEqual(self.layer_sync_flow._layer_arn, "layer_version_arn")

    def test_setup_with_unknown_layer(self):
        given_layer_name_with_hashes = f"SomeOtherLayerabcdefghij"
        self.layer_sync_flow._physical_id_mapping = {given_layer_name_with_hashes: "layer_version_arn"}
        with patch.object(self.layer_sync_flow, "_session") as _:
            with patch.object(SyncFlow, "set_up") as _:
                with self.assertRaises(MissingPhysicalResourceError):
                    self.layer_sync_flow.set_up()

    @patch("samcli.lib.sync.flows.layer_sync_flow.ApplicationBuilder")
    @patch("samcli.lib.sync.flows.layer_sync_flow.tempfile")
    @patch("samcli.lib.sync.flows.layer_sync_flow.make_zip")
    @patch("samcli.lib.sync.flows.layer_sync_flow.file_checksum")
    @patch("samcli.lib.sync.flows.layer_sync_flow.os")
    def test_setup_gather_resources(
        self, patched_os, patched_file_checksum, patched_make_zip, patched_tempfile, patched_app_builder
    ):
        given_collect_build_resources = Mock()
        self.build_context_mock.collect_build_resources.return_value = given_collect_build_resources

        given_app_builder = Mock()
        given_artifact_folder = Mock()
        given_app_builder.build().artifacts.get.return_value = given_artifact_folder
        patched_app_builder.return_value = given_app_builder

        given_zip_location = Mock()
        patched_make_zip.return_value = given_zip_location

        given_file_checksum = Mock()
        patched_file_checksum.return_value = given_file_checksum

        self.layer_sync_flow._get_lock_chain = MagicMock()

        self.layer_sync_flow.gather_resources()

        self.build_context_mock.collect_build_resources.assert_called_with(self.layer_identifier)

        patched_app_builder.assert_called_with(
            given_collect_build_resources,
            self.build_context_mock.build_dir,
            self.build_context_mock.base_dir,
            self.build_context_mock.cache_dir,
            cached=True,
            is_building_specific_resource=True,
            manifest_path_override=self.build_context_mock.manifest_path_override,
            container_manager=self.build_context_mock.container_manager,
            mode=self.build_context_mock.mode,
        )

        patched_tempfile.gettempdir.assert_called_once()
        patched_os.path.join.assert_called_with(ANY, ANY)
        patched_make_zip.assert_called_with(ANY, self.layer_sync_flow._artifact_folder)

        patched_file_checksum.assert_called_with(ANY, ANY)

        self.assertEqual(self.layer_sync_flow._artifact_folder, given_artifact_folder)
        self.assertEqual(self.layer_sync_flow._zip_file, given_zip_location)
        self.assertEqual(self.layer_sync_flow._local_sha, given_file_checksum)

        self.layer_sync_flow._get_lock_chain.assert_called_once()
        self.layer_sync_flow._get_lock_chain.return_value.__enter__.assert_called_once()
        self.layer_sync_flow._get_lock_chain.return_value.__exit__.assert_called_once()

    def test_compare_remote(self):
        given_lambda_client = Mock()
        self.layer_sync_flow._lambda_client = given_lambda_client

        given_sha256 = base64.b64encode(b"checksum")
        given_layer_info = {"Content": {"CodeSha256": given_sha256}}
        given_lambda_client.get_layer_version.return_value = given_layer_info

        self.layer_sync_flow._local_sha = base64.b64decode(given_sha256).hex()

        with patch.object(self.layer_sync_flow, "_get_latest_layer_version") as patched_get_latest_layer_version:
            given_layer_name = Mock()
            given_latest_layer_version = Mock()
            self.layer_sync_flow._layer_arn = given_layer_name
            patched_get_latest_layer_version.return_value = given_latest_layer_version

            compare_result = self.layer_sync_flow.compare_remote()

            self.assertTrue(compare_result)

    def test_sync(self):
        with patch.object(self.layer_sync_flow, "_publish_new_layer_version") as patched_publish_new_layer_version:
            with patch.object(self.layer_sync_flow, "_delete_old_layer_version") as patched_delete_old_layer_version:
                given_layer_version = Mock()
                patched_publish_new_layer_version.return_value = given_layer_version

                self.layer_sync_flow.sync()
                self.assertEqual(self.layer_sync_flow._new_layer_version, given_layer_version)

                patched_publish_new_layer_version.assert_called_once()
                patched_delete_old_layer_version.assert_called_once()

    def test_publish_new_layer_version(self):
        given_layer_name = Mock()

        given_lambda_client = Mock()
        self.layer_sync_flow._lambda_client = given_lambda_client

        given_zip_file = Mock()
        self.layer_sync_flow._zip_file = given_zip_file

        self.layer_sync_flow._layer_arn = given_layer_name

        with patch.object(self.layer_sync_flow, "_get_resource") as patched_get_resource:
            with patch("builtins.open", mock_open(read_data="data")) as mock_file:
                given_publish_layer_result = {"Version": 24}
                given_lambda_client.publish_layer_version.return_value = given_publish_layer_result

                given_layer_resource = Mock()
                patched_get_resource.return_value = given_layer_resource

                result_version = self.layer_sync_flow._publish_new_layer_version()

                patched_get_resource.assert_called_with(self.layer_identifier)
                given_lambda_client.publish_layer_version.assert_called_with(
                    LayerName=given_layer_name,
                    Content={"ZipFile": "data"},
                    CompatibleRuntimes=given_layer_resource.get("Properties", {}).get("CompatibleRuntimes", []),
                )

                self.assertEqual(result_version, given_publish_layer_result.get("Version"))

    def test_delete_old_layer_version(self):
        given_layer_name = Mock()
        given_layer_version = Mock()

        given_lambda_client = Mock()
        self.layer_sync_flow._lambda_client = given_lambda_client

        self.layer_sync_flow._layer_arn = given_layer_name
        self.layer_sync_flow._old_layer_version = given_layer_version

        self.layer_sync_flow._delete_old_layer_version()

        given_lambda_client.delete_layer_version.assert_called_with(
            LayerName=given_layer_name, VersionNumber=given_layer_version
        )

    @patch("samcli.lib.sync.flows.layer_sync_flow.os")
    @patch("samcli.lib.sync.flows.layer_sync_flow.SamFunctionProvider")
    @patch("samcli.lib.sync.flows.layer_sync_flow.FunctionLayerReferenceSync")
    def test_gather_dependencies(self, patched_function_ref_sync, patched_function_provider, os_mock):
        self.layer_sync_flow._new_layer_version = "given_new_layer_version_arn"

        given_function_provider = Mock()
        patched_function_provider.return_value = given_function_provider

        mock_some_random_layer = PropertyMock()
        mock_some_random_layer.full_path = "SomeRandomLayer"

        mock_given_layer = PropertyMock()
        mock_given_layer.full_path = self.layer_identifier

        mock_some_nested_layer = PropertyMock()
        mock_some_nested_layer.full_path = "NestedStack1/" + self.layer_identifier

        mock_function_a = PropertyMock(layers=[mock_some_random_layer])
        mock_function_a.full_path = "FunctionA"

        mock_function_b = PropertyMock(layers=[mock_given_layer])
        mock_function_b.full_path = "FunctionB"

        mock_function_c = PropertyMock(layers=[mock_some_nested_layer])
        mock_function_c.full_path = "NestedStack1/FunctionC"

        given_layers = [
            mock_function_a,
            mock_function_b,
            mock_function_c,
        ]
        given_function_provider.get_all.return_value = given_layers

        self.layer_sync_flow._stacks = Mock()

        given_layer_physical_name = Mock()
        self.layer_sync_flow._layer_arn = given_layer_physical_name

        self.layer_sync_flow._zip_file = Mock()

        dependencies = self.layer_sync_flow.gather_dependencies()

        patched_function_ref_sync.assert_called_once_with(
            "FunctionB",
            given_layer_physical_name,
            self.layer_sync_flow._new_layer_version,
            self.layer_sync_flow._build_context,
            self.layer_sync_flow._deploy_context,
            self.layer_sync_flow._physical_id_mapping,
            self.layer_sync_flow._stacks,
        )

        self.assertEqual(len(dependencies), 1)

    @patch("samcli.lib.sync.flows.layer_sync_flow.os")
    @patch("samcli.lib.sync.flows.layer_sync_flow.SamFunctionProvider")
    @patch("samcli.lib.sync.flows.layer_sync_flow.FunctionLayerReferenceSync")
    def test_gather_dependencies_nested_stack(self, patched_function_ref_sync, patched_function_provider, os_mock):
        self.layer_identifier = "NestedStack1/Layer1"
        self.layer_sync_flow._layer_identifier = "NestedStack1/Layer1"
        self.layer_sync_flow._new_layer_version = "given_new_layer_version_arn"

        given_function_provider = Mock()
        patched_function_provider.return_value = given_function_provider

        mock_some_random_layer = PropertyMock()
        mock_some_random_layer.full_path = "Layer1"

        mock_given_layer = PropertyMock()
        mock_given_layer.full_path = self.layer_identifier

        mock_some_nested_layer = PropertyMock()
        mock_some_nested_layer.full_path = "NestedStack1/Layer2"

        mock_function_a = PropertyMock(layers=[mock_some_random_layer])
        mock_function_a.full_path = "FunctionA"

        mock_function_b = PropertyMock(layers=[mock_given_layer])
        mock_function_b.full_path = "NestedStack1/FunctionB"

        mock_function_c = PropertyMock(layers=[mock_some_nested_layer])
        mock_function_c.full_path = "NestedStack1/FunctionC"

        given_layers = [
            mock_function_a,
            mock_function_b,
            mock_function_c,
        ]
        given_function_provider.get_all.return_value = given_layers

        self.layer_sync_flow._stacks = Mock()

        given_layer_physical_name = Mock()
        self.layer_sync_flow._layer_arn = given_layer_physical_name

        self.layer_sync_flow._zip_file = Mock()

        dependencies = self.layer_sync_flow.gather_dependencies()

        patched_function_ref_sync.assert_called_once_with(
            "NestedStack1/FunctionB",
            given_layer_physical_name,
            self.layer_sync_flow._new_layer_version,
            self.layer_sync_flow._build_context,
            self.layer_sync_flow._deploy_context,
            self.layer_sync_flow._physical_id_mapping,
            self.layer_sync_flow._stacks,
        )

        self.assertEqual(len(dependencies), 1)

    def test_get_latest_layer_version(self):
        given_version = Mock()
        given_layer_name = Mock()
        given_lambda_client = Mock()
        given_lambda_client.list_layer_versions.return_value = {"LayerVersions": [{"Version": given_version}]}
        self.layer_sync_flow._lambda_client = given_lambda_client
        self.layer_sync_flow._layer_arn = given_layer_name

        latest_layer_version = self.layer_sync_flow._get_latest_layer_version()

        given_lambda_client.list_layer_versions.assert_called_with(LayerName=given_layer_name)
        self.assertEqual(latest_layer_version, given_version)

    def test_get_latest_layer_version_error(self):
        given_layer_name = Mock()
        given_lambda_client = Mock()
        given_lambda_client.list_layer_versions.return_value = {"LayerVersions": []}
        self.layer_sync_flow._lambda_client = given_lambda_client
        self.layer_sync_flow._layer_arn = given_layer_name

        with self.assertRaises(NoLayerVersionsFoundError):
            self.layer_sync_flow._get_latest_layer_version()

    def test_equality_keys(self):
        self.assertEqual(self.layer_sync_flow._equality_keys(), self.layer_identifier)

    @patch("samcli.lib.sync.flows.layer_sync_flow.ResourceAPICall")
    def test_get_resource_api_calls(self, resource_api_call_mock):
        result = self.layer_sync_flow._get_resource_api_calls()
        self.assertEqual(len(result), 1)
        resource_api_call_mock.assert_called_once_with(self.layer_identifier, ["Build"])


class TestFunctionLayerReferenceSync(TestCase):
    def setUp(self):
        self.function_identifier = "function"
        self.layer_name = "Layer1"
        self.old_layer_version = 1
        self.new_layer_version = 2

        self.function_layer_sync = FunctionLayerReferenceSync(
            self.function_identifier, self.layer_name, self.new_layer_version, Mock(), Mock(), {}, []
        )

    @patch("samcli.lib.sync.sync_flow.get_boto_client_provider_from_session_with_config")
    def test_setup(self, client_provider_mock):
        with patch.object(self.function_layer_sync, "_session") as patched_session:
            with patch.object(SyncFlow, "set_up") as patched_super_setup:
                self.function_layer_sync.set_up()

                patched_super_setup.assert_called_once()
                client_provider_mock.return_value.assert_called_with("lambda")

    def test_sync(self):
        given_lambda_client = Mock()
        self.function_layer_sync._lambda_client = given_lambda_client

        other_layer_version_arn = "SomeOtherLayerVersionArn"
        given_function_result = {"Configuration": {"Layers": [{"Arn": "Layer1:1"}, {"Arn": other_layer_version_arn}]}}
        given_lambda_client.get_function.return_value = given_function_result

        with patch.object(self.function_layer_sync, "get_physical_id") as patched_get_physical_id:
            with patch.object(self.function_layer_sync, "_locks") as patched_locks:
                given_physical_id = Mock()
                patched_get_physical_id.return_value = given_physical_id

                self.function_layer_sync.sync()

                patched_get_physical_id.assert_called_with(self.function_identifier)

                patched_locks.get.assert_called_with(
                    SyncFlow._get_lock_key(
                        self.function_identifier, FunctionLayerReferenceSync.UPDATE_FUNCTION_CONFIGURATION
                    )
                )

                given_lambda_client.get_function.assert_called_with(FunctionName=given_physical_id)

                given_lambda_client.update_function_configuration.assert_called_with(
                    FunctionName=given_physical_id, Layers=[other_layer_version_arn, "Layer1:2"]
                )

    def test_sync_with_existing_new_layer_version_arn(self):
        given_lambda_client = Mock()
        self.function_layer_sync._lambda_client = given_lambda_client

        given_function_result = {"Configuration": {"Layers": [{"Arn": "Layer1:2"}]}}
        given_lambda_client.get_function.return_value = given_function_result

        with patch.object(self.function_layer_sync, "get_physical_id") as patched_get_physical_id:
            with patch.object(self.function_layer_sync, "_locks") as patched_locks:
                given_physical_id = Mock()
                patched_get_physical_id.return_value = given_physical_id

                self.function_layer_sync.sync()

                patched_locks.get.assert_called_with(
                    SyncFlow._get_lock_key(
                        self.function_identifier, FunctionLayerReferenceSync.UPDATE_FUNCTION_CONFIGURATION
                    )
                )

                patched_get_physical_id.assert_called_with(self.function_identifier)

                given_lambda_client.get_function.assert_called_with(FunctionName=given_physical_id)

                given_lambda_client.update_function_configuration.assert_not_called()

    def test_equality_keys(self):
        self.assertEqual(
            self.function_layer_sync._equality_keys(),
            (self.function_identifier, self.layer_name, self.new_layer_version),
        )

    def test_compare_remote(self):
        self.assertFalse(self.function_layer_sync.compare_remote())

    def test_gather_dependencies(self):
        self.assertEqual(self.function_layer_sync.gather_dependencies(), [])
