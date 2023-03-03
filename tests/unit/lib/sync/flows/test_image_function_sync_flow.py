from samcli.lib.sync.sync_flow import ApiCallTypes
from unittest import TestCase
from unittest.mock import MagicMock, patch

from samcli.lib.sync.flows.image_function_sync_flow import ImageFunctionSyncFlow
from samcli.lib.utils.hash import str_checksum


class TestImageFunctionSyncFlow(TestCase):
    def create_function_sync_flow(self):
        sync_flow = ImageFunctionSyncFlow(
            "Function1",
            build_context=MagicMock(),
            deploy_context=MagicMock(),
            sync_context=MagicMock(),
            physical_id_mapping={},
            stacks=[MagicMock()],
        )
        return sync_flow

    @patch("samcli.lib.sync.flows.image_function_sync_flow.docker")
    def test_get_docker_client(self, patched_docker):
        sync_flow = self.create_function_sync_flow()
        self.assertIsNone(sync_flow._docker_client)

        docker_client = sync_flow._get_docker_client()
        self.assertIsNotNone(docker_client)
        self.assertIsNotNone(sync_flow._docker_client)
        patched_docker.from_env.assert_called_once()

        patched_docker.reset_mock()
        docker_client = sync_flow._get_docker_client()
        self.assertIsNotNone(docker_client)
        self.assertIsNotNone(sync_flow._docker_client)
        patched_docker.from_env.assert_not_called()

    @patch("samcli.lib.sync.flows.image_function_sync_flow.ImageFunctionSyncFlow._boto_client")
    def test_get_ecr_client(self, patched_boto_client):
        sync_flow = self.create_function_sync_flow()
        self.assertIsNone(sync_flow._ecr_client)

        ecr_client = sync_flow._get_ecr_client()
        self.assertIsNotNone(ecr_client)
        self.assertIsNotNone(sync_flow._ecr_client)
        patched_boto_client.assert_called_once()

        patched_boto_client.reset_mock()

        ecr_client = sync_flow._get_ecr_client()
        self.assertIsNotNone(ecr_client)
        self.assertIsNotNone(sync_flow._ecr_client)
        patched_boto_client.assert_not_called()

    @patch("samcli.lib.sync.flows.image_function_sync_flow.ApplicationBuilder")
    @patch("samcli.lib.sync.sync_flow.Session")
    def test_gather_resources(self, session_mock, builder_mock):
        get_mock = MagicMock()
        get_mock.return_value = "ImageName1"
        builder_mock.return_value.build.return_value.artifacts.get = get_mock
        sync_flow = self.create_function_sync_flow()

        with patch.object(sync_flow, "_get_docker_client") as patched_get_docker_client:
            sync_flow.set_up()
            sync_flow.gather_resources()

            get_mock.assert_called_once_with("Function1")
            self.assertEqual(sync_flow._image_name, "ImageName1")
            self.assertEqual(
                sync_flow._local_sha, str(patched_get_docker_client().images.get("ImageName1").attrs.get("Id"))
            )

    @patch("samcli.lib.sync.flows.image_function_sync_flow.wait_for_function_update_complete")
    @patch("samcli.lib.sync.flows.image_function_sync_flow.ECRUploader")
    @patch("samcli.lib.sync.sync_flow.Session")
    def test_sync_context_image_repo(self, session_mock, uploader_mock, wait_mock):
        sync_flow = self.create_function_sync_flow()
        sync_flow._image_name = "ImageName1"

        uploader_mock.return_value.upload.return_value = "image_uri"

        sync_flow._get_lock_chain = MagicMock()
        sync_flow.has_locks = MagicMock()

        sync_flow.get_physical_id = MagicMock()
        sync_flow.get_physical_id.return_value = "PhysicalFunction1"
        sync_flow._deploy_context.image_repository = "repo_uri"

        sync_flow.set_up()
        sync_flow.sync()

        uploader_mock.return_value.upload.assert_called_once_with("ImageName1", "Function1")
        uploader_mock.assert_called_once_with(sync_flow._docker_client, sync_flow._ecr_client, "repo_uri", None)

        sync_flow._get_lock_chain.assert_called_once()
        sync_flow._get_lock_chain.return_value.__enter__.assert_called_once()
        sync_flow._lambda_client.update_function_code.assert_called_once_with(
            FunctionName="PhysicalFunction1", ImageUri="image_uri"
        )
        wait_mock.assert_called_once_with(sync_flow._lambda_client, "PhysicalFunction1")
        sync_flow._get_lock_chain.return_value.__exit__.assert_called_once()

    @patch("samcli.lib.sync.flows.image_function_sync_flow.wait_for_function_update_complete")
    @patch("samcli.lib.sync.flows.image_function_sync_flow.ECRUploader")
    @patch("samcli.lib.sync.sync_flow.Session")
    def test_sync_context_image_repos(self, session_mock, uploader_mock, wait_mock):
        sync_flow = self.create_function_sync_flow()
        sync_flow._image_name = "ImageName1"

        uploader_mock.return_value.upload.return_value = "image_uri"

        sync_flow._get_lock_chain = MagicMock()
        sync_flow.has_locks = MagicMock()

        sync_flow.get_physical_id = MagicMock()
        sync_flow.get_physical_id.return_value = "PhysicalFunction1"
        sync_flow._deploy_context.image_repository = ""
        sync_flow._deploy_context.image_repositories = {"Function1": "repo_uri"}

        sync_flow.set_up()
        sync_flow.sync()

        uploader_mock.return_value.upload.assert_called_once_with("ImageName1", "Function1")
        uploader_mock.assert_called_once_with(sync_flow._docker_client, sync_flow._ecr_client, "repo_uri", None)

        sync_flow._get_lock_chain.assert_called_once()
        sync_flow._get_lock_chain.return_value.__enter__.assert_called_once()
        sync_flow._lambda_client.update_function_code.assert_called_once_with(
            FunctionName="PhysicalFunction1", ImageUri="image_uri"
        )
        wait_mock.assert_called_once_with(sync_flow._lambda_client, "PhysicalFunction1")
        sync_flow._get_lock_chain.return_value.__exit__.assert_called_once()

    @patch("samcli.lib.sync.flows.image_function_sync_flow.wait_for_function_update_complete")
    @patch("samcli.lib.sync.flows.image_function_sync_flow.ECRUploader")
    @patch("samcli.lib.sync.sync_flow.Session")
    def test_sync_remote_image_repo(self, session_mock, uploader_mock, wait_mock):
        sync_flow = self.create_function_sync_flow()
        sync_flow._image_name = "ImageName1"

        uploader_mock.return_value.upload.return_value = "image_uri"

        sync_flow._get_lock_chain = MagicMock()
        sync_flow.has_locks = MagicMock()

        sync_flow.get_physical_id = MagicMock()
        sync_flow.get_physical_id.return_value = "PhysicalFunction1"
        sync_flow._deploy_context.image_repository = ""
        sync_flow._deploy_context.image_repositories = {}

        sync_flow.set_up()

        sync_flow._lambda_client.get_function = MagicMock()
        sync_flow._lambda_client.get_function.return_value = {"Code": {"ImageUri": "repo_uri:tag"}}

        sync_flow.sync()

        uploader_mock.return_value.upload.assert_called_once_with("ImageName1", "Function1")
        uploader_mock.assert_called_once_with(sync_flow._docker_client, sync_flow._ecr_client, "repo_uri", None)

        sync_flow._get_lock_chain.assert_called_once()
        sync_flow._get_lock_chain.return_value.__enter__.assert_called_once()
        sync_flow._lambda_client.update_function_code.assert_called_once_with(
            FunctionName="PhysicalFunction1", ImageUri="image_uri"
        )
        wait_mock.assert_called_once_with(sync_flow._lambda_client, "PhysicalFunction1")
        sync_flow._get_lock_chain.return_value.__exit__.assert_called_once()

    @patch("samcli.lib.sync.flows.image_function_sync_flow.ECRUploader")
    @patch("samcli.lib.sync.sync_flow.Session")
    def test_sync_with_no_image(self, session_mock, uploader_mock):
        sync_flow = self.create_function_sync_flow()
        sync_flow._image_name = None
        sync_flow.sync()
        uploader_mock.return_value.upload.assert_not_called()

    def test_compare_remote(self):
        sync_flow = self.create_function_sync_flow()
        self.assertFalse(sync_flow.compare_remote())

    @patch("samcli.lib.sync.flows.image_function_sync_flow.ResourceAPICall")
    def test_get_resource_api_calls(self, resource_api_call_mock):
        sync_flow = self.create_function_sync_flow()
        result = sync_flow._get_resource_api_calls()
        self.assertEqual(len(result), 1)
        resource_api_call_mock.assert_any_call(
            "Function1", [ApiCallTypes.UPDATE_FUNCTION_CODE, ApiCallTypes.UPDATE_FUNCTION_CONFIGURATION]
        )
