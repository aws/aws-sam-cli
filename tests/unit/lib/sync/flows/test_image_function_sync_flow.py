from samcli.lib.sync.sync_flow import SyncFlow
from unittest import TestCase
from unittest.mock import ANY, MagicMock, call, patch

from samcli.lib.sync.flows.image_function_sync_flow import ImageFunctionSyncFlow


class TestImageFunctionSyncFlow(TestCase):
    def create_function_sync_flow(self):
        sync_flow = ImageFunctionSyncFlow(
            "Function1",
            build_context=MagicMock(),
            deploy_context=MagicMock(),
            physical_id_mapping={},
            stacks=[MagicMock()],
            docker_client=MagicMock(),
        )
        return sync_flow

    @patch("samcli.lib.sync.sync_flow.get_boto_client_provider_from_session_with_config")
    @patch("samcli.lib.sync.sync_flow.Session")
    def test_set_up(self, session_mock, client_provider_mock):
        sync_flow = self.create_function_sync_flow()
        sync_flow.set_up()
        client_provider_mock.return_value.assert_any_call("lambda")
        client_provider_mock.return_value.assert_any_call("ecr")

    @patch("samcli.lib.sync.flows.image_function_sync_flow.ApplicationBuilder")
    @patch("samcli.lib.sync.sync_flow.Session")
    def test_gather_resources(self, session_mock, builder_mock):
        get_mock = MagicMock()
        get_mock.return_value = "ImageName1"
        builder_mock.return_value.build.return_value.artifacts.get = get_mock
        sync_flow = self.create_function_sync_flow()

        sync_flow.set_up()
        sync_flow.gather_resources()

        get_mock.assert_called_once_with("Function1")
        self.assertEqual(sync_flow._image_name, "ImageName1")

    @patch("samcli.lib.sync.flows.image_function_sync_flow.ECRUploader")
    @patch("samcli.lib.sync.sync_flow.Session")
    def test_sync_context_image_repo(self, session_mock, uploader_mock):
        sync_flow = self.create_function_sync_flow()
        sync_flow._image_name = "ImageName1"

        uploader_mock.return_value.upload.return_value = "image_uri"

        sync_flow.get_physical_id = MagicMock()
        sync_flow.get_physical_id.return_value = "PhysicalFunction1"
        sync_flow._deploy_context.image_repository = "repo_uri"

        sync_flow.set_up()
        sync_flow.sync()

        uploader_mock.return_value.upload.assert_called_once_with("ImageName1", "Function1")
        uploader_mock.assert_called_once_with(sync_flow._docker_client, sync_flow._ecr_client, "repo_uri", None)
        sync_flow._lambda_client.update_function_code.assert_called_once_with(
            FunctionName="PhysicalFunction1", ImageUri="image_uri"
        )

    @patch("samcli.lib.sync.flows.image_function_sync_flow.ECRUploader")
    @patch("samcli.lib.sync.sync_flow.Session")
    def test_sync_context_image_repos(self, session_mock, uploader_mock):
        sync_flow = self.create_function_sync_flow()
        sync_flow._image_name = "ImageName1"

        uploader_mock.return_value.upload.return_value = "image_uri"

        sync_flow.get_physical_id = MagicMock()
        sync_flow.get_physical_id.return_value = "PhysicalFunction1"
        sync_flow._deploy_context.image_repository = ""
        sync_flow._deploy_context.image_repositories = {"Function1": "repo_uri"}

        sync_flow.set_up()
        sync_flow.sync()

        uploader_mock.return_value.upload.assert_called_once_with("ImageName1", "Function1")
        uploader_mock.assert_called_once_with(sync_flow._docker_client, sync_flow._ecr_client, "repo_uri", None)
        sync_flow._lambda_client.update_function_code.assert_called_once_with(
            FunctionName="PhysicalFunction1", ImageUri="image_uri"
        )

    @patch("samcli.lib.sync.flows.image_function_sync_flow.ECRUploader")
    @patch("samcli.lib.sync.sync_flow.Session")
    def test_sync_remote_image_repo(self, session_mock, uploader_mock):
        sync_flow = self.create_function_sync_flow()
        sync_flow._image_name = "ImageName1"

        uploader_mock.return_value.upload.return_value = "image_uri"

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
        sync_flow._lambda_client.update_function_code.assert_called_once_with(
            FunctionName="PhysicalFunction1", ImageUri="image_uri"
        )

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

    def test_get_resource_api_calls(self):
        sync_flow = self.create_function_sync_flow()
        self.assertEqual(sync_flow._get_resource_api_calls(), [])
