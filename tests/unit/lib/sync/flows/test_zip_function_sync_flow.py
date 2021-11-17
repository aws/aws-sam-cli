import os
import hashlib

from samcli.lib.sync.sync_flow import SyncFlow
from unittest import TestCase
from unittest.mock import ANY, MagicMock, call, mock_open, patch

from samcli.lib.sync.flows.zip_function_sync_flow import ZipFunctionSyncFlow


class TestZipFunctionSyncFlow(TestCase):
    def create_function_sync_flow(self):
        sync_flow = ZipFunctionSyncFlow(
            "Function1",
            build_context=MagicMock(),
            deploy_context=MagicMock(),
            physical_id_mapping={},
            stacks=[MagicMock()],
        )
        sync_flow._get_resource_api_calls = MagicMock()
        return sync_flow

    @patch("samcli.lib.sync.sync_flow.get_boto_client_provider_from_session_with_config")
    @patch("samcli.lib.sync.sync_flow.Session")
    def test_set_up(self, session_mock, client_provider_mock):
        sync_flow = self.create_function_sync_flow()
        sync_flow.set_up()
        client_provider_mock.return_value.assert_any_call("lambda")
        client_provider_mock.return_value.assert_any_call("s3")

    @patch("samcli.lib.sync.flows.zip_function_sync_flow.hashlib.sha256")
    @patch("samcli.lib.sync.flows.zip_function_sync_flow.uuid.uuid4")
    @patch("samcli.lib.sync.flows.zip_function_sync_flow.file_checksum")
    @patch("samcli.lib.sync.flows.zip_function_sync_flow.make_zip")
    @patch("samcli.lib.sync.flows.zip_function_sync_flow.tempfile.gettempdir")
    @patch("samcli.lib.sync.flows.zip_function_sync_flow.ApplicationBuilder")
    @patch("samcli.lib.sync.sync_flow.Session")
    def test_gather_resources(
        self, session_mock, builder_mock, gettempdir_mock, make_zip_mock, file_checksum_mock, uuid4_mock, sha256_mock
    ):
        get_mock = MagicMock()
        get_mock.return_value = "ArtifactFolder1"
        builder_mock.return_value.build.return_value.artifacts.get = get_mock
        uuid4_mock.return_value.hex = "uuid_value"
        gettempdir_mock.return_value = "temp_folder"
        make_zip_mock.return_value = "zip_file"
        file_checksum_mock.return_value = "sha256_value"
        sync_flow = self.create_function_sync_flow()

        sync_flow._get_lock_chain = MagicMock()

        sync_flow.set_up()
        sync_flow.gather_resources()

        get_mock.assert_called_once_with("Function1")
        self.assertEqual(sync_flow._artifact_folder, "ArtifactFolder1")
        make_zip_mock.assert_called_once_with("temp_folder" + os.sep + "data-uuid_value", "ArtifactFolder1")
        file_checksum_mock.assert_called_once_with("zip_file", sha256_mock.return_value)
        self.assertEqual("sha256_value", sync_flow._local_sha)
        sync_flow._get_lock_chain.assert_called_once()
        sync_flow._get_lock_chain.return_value.__enter__.assert_called_once()
        sync_flow._get_lock_chain.return_value.__exit__.assert_called_once()

    @patch("samcli.lib.sync.flows.zip_function_sync_flow.base64.b64decode")
    @patch("samcli.lib.sync.sync_flow.Session")
    def test_compare_remote_true(self, session_mock, b64decode_mock):
        b64decode_mock.return_value.hex.return_value = "sha256_value"
        sync_flow = self.create_function_sync_flow()
        sync_flow._local_sha = "sha256_value"

        sync_flow.get_physical_id = MagicMock()
        sync_flow.get_physical_id.return_value = "PhysicalFunction1"

        sync_flow.set_up()

        sync_flow._lambda_client.get_function.return_value = {"Configuration": {"CodeSha256": "sha256_value_b64"}}

        result = sync_flow.compare_remote()

        sync_flow._lambda_client.get_function.assert_called_once_with(FunctionName="PhysicalFunction1")
        b64decode_mock.assert_called_once_with("sha256_value_b64")
        self.assertTrue(result)

    @patch("samcli.lib.sync.flows.zip_function_sync_flow.base64.b64decode")
    @patch("samcli.lib.sync.sync_flow.Session")
    def test_compare_remote_false(self, session_mock, b64decode_mock):
        b64decode_mock.return_value.hex.return_value = "sha256_value_2"
        sync_flow = self.create_function_sync_flow()
        sync_flow._local_sha = "sha256_value"

        sync_flow.get_physical_id = MagicMock()
        sync_flow.get_physical_id.return_value = "PhysicalFunction1"

        sync_flow.set_up()

        sync_flow._lambda_client.get_function.return_value = {"Configuration": {"CodeSha256": "sha256_value_b64"}}

        result = sync_flow.compare_remote()

        sync_flow._lambda_client.get_function.assert_called_once_with(FunctionName="PhysicalFunction1")
        b64decode_mock.assert_called_once_with("sha256_value_b64")
        self.assertFalse(result)

    @patch("samcli.lib.sync.flows.zip_function_sync_flow.open", mock_open(read_data=b"zip_content"), create=True)
    @patch("samcli.lib.sync.flows.zip_function_sync_flow.os.remove")
    @patch("samcli.lib.sync.flows.zip_function_sync_flow.os.path.exists")
    @patch("samcli.lib.sync.flows.zip_function_sync_flow.S3Uploader")
    @patch("samcli.lib.sync.flows.zip_function_sync_flow.os.path.getsize")
    @patch("samcli.lib.sync.sync_flow.Session")
    def test_sync_direct(self, session_mock, getsize_mock, uploader_mock, exists_mock, remove_mock):
        getsize_mock.return_value = 49 * 1024 * 1024
        exists_mock.return_value = True
        sync_flow = self.create_function_sync_flow()
        sync_flow._zip_file = "zip_file"

        sync_flow.get_physical_id = MagicMock()
        sync_flow.get_physical_id.return_value = "PhysicalFunction1"

        sync_flow.set_up()

        sync_flow.sync()

        sync_flow._lambda_client.update_function_code.assert_called_once_with(
            FunctionName="PhysicalFunction1", ZipFile=b"zip_content"
        )
        remove_mock.assert_called_once_with("zip_file")

    @patch("samcli.lib.sync.flows.zip_function_sync_flow.open", mock_open(read_data=b"zip_content"), create=True)
    @patch("samcli.lib.sync.flows.zip_function_sync_flow.os.remove")
    @patch("samcli.lib.sync.flows.zip_function_sync_flow.os.path.exists")
    @patch("samcli.lib.sync.flows.zip_function_sync_flow.S3Uploader")
    @patch("samcli.lib.sync.flows.zip_function_sync_flow.os.path.getsize")
    @patch("samcli.lib.sync.sync_flow.Session")
    def test_sync_s3(self, session_mock, getsize_mock, uploader_mock, exists_mock, remove_mock):
        getsize_mock.return_value = 51 * 1024 * 1024
        exists_mock.return_value = True
        uploader_mock.return_value.upload_with_dedup.return_value = "s3://bucket_name/bucket/key"
        sync_flow = self.create_function_sync_flow()
        sync_flow._zip_file = "zip_file"
        sync_flow._deploy_context.s3_bucket = "bucket_name"

        sync_flow.get_physical_id = MagicMock()
        sync_flow.get_physical_id.return_value = "PhysicalFunction1"

        sync_flow.set_up()

        sync_flow.sync()

        uploader_mock.return_value.upload_with_dedup.assert_called_once_with("zip_file")

        sync_flow._lambda_client.update_function_code.assert_called_once_with(
            FunctionName="PhysicalFunction1", S3Bucket="bucket_name", S3Key="bucket/key"
        )
        remove_mock.assert_called_once_with("zip_file")

    @patch("samcli.lib.sync.flows.zip_function_sync_flow.ResourceAPICall")
    def test_get_resource_api_calls(self, resource_api_call_mock):
        build_context = MagicMock()
        layer1 = MagicMock()
        layer2 = MagicMock()
        layer1.full_path = "Layer1"
        layer2.full_path = "Layer2"
        function_mock = MagicMock()
        function_mock.layers = [layer1, layer2]
        build_context.function_provider.functions.get.return_value = function_mock
        sync_flow = ZipFunctionSyncFlow(
            "Function1",
            build_context=build_context,
            deploy_context=MagicMock(),
            physical_id_mapping={},
            stacks=[MagicMock()],
        )

        result = sync_flow._get_resource_api_calls()
        self.assertEqual(len(result), 2)
        resource_api_call_mock.assert_any_call("Layer1", ["Build"])
        resource_api_call_mock.assert_any_call("Layer2", ["Build"])

    def test_combine_dependencies(self):
        sync_flow = self.create_function_sync_flow()
        self.assertTrue(sync_flow._combine_dependencies())
