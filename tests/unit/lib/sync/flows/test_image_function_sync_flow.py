from unittest import TestCase
import unittest
from unittest.mock import MagicMock, patch, Mock

from parameterized import parameterized, parameterized_class

from samcli.lib.providers.provider import CapacityProviderConfig
from samcli.lib.sync.flows.image_function_sync_flow import ImageFunctionSyncFlow
from samcli.lib.sync.sync_flow import ApiCallTypes


@parameterized_class(
    ("build_artifacts", "has_capacity_provider_config"),
    [
        (None, False),
        (Mock(), True),
    ],
)
class TestImageFunctionSyncFlow(TestCase):
    build_artifacts = None
    has_capacity_provider_config = None

    def create_function_sync_flow(self, publish_to_latest_published=False):
        sync_context = MagicMock()

        function_mock = MagicMock()
        function_mock.codeuri = "CodeUri/"
        function_mock.capacity_provider_config = (
            {
                "Arn": "arn:aws:lambda:us-east-1:123456789012:capacity-provider:my-capacity-provider-name",
                "PerExecutionEnvironmentMaxConcurrency": 8,
            }
            if self.has_capacity_provider_config
            else None
        )
        # Mock the capacity_provider_configuration property to return the correct value
        function_mock.capacity_provider_configuration = (
            CapacityProviderConfig.from_dict(function_mock.capacity_provider_config)
            if self.has_capacity_provider_config
            else None
        )
        function_mock.publish_to_latest_published = publish_to_latest_published

        build_context = MagicMock()
        build_context.function_provider.get.return_value = function_mock

        sync_flow = ImageFunctionSyncFlow(
            "Function1",
            build_context=build_context,
            deploy_context=MagicMock(),
            sync_context=sync_context,
            physical_id_mapping={},
            stacks=[MagicMock()],
            application_build_result=self.build_artifacts,
        )
        return sync_flow

    @patch("samcli.lib.sync.flows.image_function_sync_flow.get_validated_container_client")
    def test_get_docker_client(self, patched_get_validated_client):
        sync_flow = self.create_function_sync_flow()
        self.assertIsNone(sync_flow._docker_client)

        docker_client = sync_flow._get_docker_client()
        self.assertIsNotNone(docker_client)
        self.assertIsNotNone(sync_flow._docker_client)
        patched_get_validated_client.assert_called_once()

        patched_get_validated_client.reset_mock()
        docker_client = sync_flow._get_docker_client()
        self.assertIsNotNone(docker_client)
        self.assertIsNotNone(sync_flow._docker_client)
        patched_get_validated_client.assert_not_called()

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

            if self.build_artifacts:
                get_mock.assert_not_called()
                self.assertEqual(
                    sync_flow._image_name, self.build_artifacts.artifacts.get(sync_flow._function_identifier)
                )
            else:
                get_mock.assert_called_once_with("Function1")
                self.assertEqual(sync_flow._image_name, "ImageName1")
            self.assertEqual(
                sync_flow._local_sha, str(patched_get_docker_client().images.get("ImageName1").attrs.get("Id"))
            )

    @patch("samcli.lib.sync.flows.image_function_sync_flow.get_validated_container_client")
    @patch("samcli.lib.sync.flows.function_sync_flow.wait_for_function_update_complete")
    @patch("samcli.lib.sync.flows.image_function_sync_flow.ECRUploader")
    @patch("samcli.lib.sync.sync_flow.Session")
    def test_sync_context_image_repo(self, session_mock, uploader_mock, wait_mock, mock_get_validated_client):
        # Mock the docker client
        docker_client_mock = MagicMock()
        mock_get_validated_client.return_value = docker_client_mock

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

    @patch("samcli.lib.sync.flows.image_function_sync_flow.get_validated_container_client")
    @patch("samcli.lib.sync.flows.function_sync_flow.wait_for_function_update_complete")
    @patch("samcli.lib.sync.flows.image_function_sync_flow.ECRUploader")
    @patch("samcli.lib.sync.sync_flow.Session")
    def test_sync_context_image_repos(self, session_mock, uploader_mock, wait_mock, mock_get_validated_client):
        # Mock the docker client
        docker_client_mock = MagicMock()
        mock_get_validated_client.return_value = docker_client_mock

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

    @patch("samcli.lib.sync.flows.image_function_sync_flow.get_validated_container_client")
    @patch("samcli.lib.sync.flows.function_sync_flow.wait_for_function_update_complete")
    @patch("samcli.lib.sync.flows.image_function_sync_flow.ECRUploader")
    @patch("samcli.lib.sync.sync_flow.Session")
    def test_sync_remote_image_repo(self, session_mock, uploader_mock, wait_mock, mock_get_validated_client):
        # Mock the docker client
        docker_client_mock = MagicMock()
        mock_get_validated_client.return_value = docker_client_mock

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

    @unittest.skipIf(
        lambda self: not self.has_capacity_provider_config,
        "Skip publish latest invocable test for function withouth capacity provider config",
    )
    @patch("samcli.lib.sync.flows.function_sync_flow.wait_for_function_update_complete")
    @patch("samcli.lib.sync.flows.image_function_sync_flow.ECRUploader")
    @patch("samcli.lib.sync.sync_flow.Session")
    def test_sync_remote_image_repo_with_publish_function(self, session_mock, uploader_mock, wait_mock):
        sync_flow = self.create_function_sync_flow(publish_to_latest_published=True)
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
        sync_flow._lambda_client.publish_version = MagicMock()
        sync_flow._lambda_client.publish_version.return_value = {"Version": "$LATEST.PUBLISHED"}

        sync_flow.sync()

        uploader_mock.return_value.upload.assert_called_once_with("ImageName1", "Function1")
        uploader_mock.assert_called_once_with(sync_flow._docker_client, sync_flow._ecr_client, "repo_uri", None)

        self.assertEqual(sync_flow._get_lock_chain.call_count, 2)
        self.assertEqual(sync_flow._get_lock_chain.return_value.__enter__.call_count, 2)
        sync_flow._lambda_client.update_function_code.assert_called_once_with(
            FunctionName="PhysicalFunction1", ImageUri="image_uri"
        )
        self.assertEqual(wait_mock.call_count, 2)
        self.assertEqual(
            wait_mock.call_args_list,
            [
                ((sync_flow._lambda_client, "PhysicalFunction1"),),
                ((sync_flow._lambda_client, "PhysicalFunction1", "$LATEST.PUBLISHED"),),
            ],
        )
        self.assertEqual(sync_flow._get_lock_chain.return_value.__exit__.call_count, 2)

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

    @parameterized.expand(
        [
            # publish_to_latest_published, has_capacity_provider_config, expect_api_list
            (False, False, [ApiCallTypes.UPDATE_FUNCTION_CODE, ApiCallTypes.UPDATE_FUNCTION_CONFIGURATION]),
            (False, True, [ApiCallTypes.UPDATE_FUNCTION_CODE, ApiCallTypes.UPDATE_FUNCTION_CONFIGURATION]),
            (True, False, [ApiCallTypes.UPDATE_FUNCTION_CODE, ApiCallTypes.UPDATE_FUNCTION_CONFIGURATION]),
            (
                True,
                True,
                [
                    ApiCallTypes.UPDATE_FUNCTION_CODE,
                    ApiCallTypes.UPDATE_FUNCTION_CONFIGURATION,
                    ApiCallTypes.PUBLISH_VERSION,
                ],
            ),
        ]
    )
    @patch("samcli.lib.sync.flows.image_function_sync_flow.ResourceAPICall")
    def test_get_resource_api_calls(
        self, publish_to_latest_published, has_capacity_provider_config, expect_api_list, resource_api_call_mock
    ):
        sync_context = MagicMock()

        function_mock = MagicMock()
        function_mock.codeuri = "CodeUri/"
        function_mock.capacity_provider_config = (
            {
                "Arn": "arn:aws:lambda:us-east-1:123456789012:capacity-provider:my-capacity-provider-name",
                "PerExecutionEnvironmentMaxConcurrency": 8,
            }
            if has_capacity_provider_config
            else None
        )
        # Mock the capacity_provider_configuration property to return the correct value
        function_mock.capacity_provider_configuration = (
            CapacityProviderConfig.from_dict(function_mock.capacity_provider_config)
            if has_capacity_provider_config
            else None
        )
        function_mock.publish_to_latest_published = publish_to_latest_published

        build_context = MagicMock()
        build_context.function_provider.get.return_value = function_mock

        sync_flow = ImageFunctionSyncFlow(
            "Function1",
            build_context=build_context,
            deploy_context=MagicMock(),
            sync_context=sync_context,
            physical_id_mapping={},
            stacks=[MagicMock()],
            application_build_result=self.build_artifacts,
        )

        result = sync_flow._get_resource_api_calls()
        self.assertEqual(len(result), 1)
        resource_api_call_mock.assert_any_call("Function1", expect_api_list)
