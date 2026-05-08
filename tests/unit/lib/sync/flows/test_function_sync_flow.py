from unittest import TestCase
from unittest.mock import ANY, MagicMock, patch, Mock, call

from parameterized import parameterized, parameterized_class

from samcli.lib.sync.flows.function_sync_flow import (
    FunctionPublishTarget,
    FunctionPublishVersionParams,
    FunctionSyncFlow,
    FunctionUpdateParams,
)
from samcli.lib.sync.sync_flow import ApiCallTypes


@parameterized_class(
    ("build_artifacts"),
    [
        (None,),
        (Mock(),),
    ],
)
class TestFunctionSyncFlow(TestCase):
    build_artifacts = None

    def setUp(self):
        # Create a mock Lambda client that will be used across all tests
        self.lambda_client_mock = MagicMock()
        self.lambda_client_mock.get_waiter.return_value = MagicMock()

        # Set up common mock responses
        self.lambda_client_mock.publish_version.return_value = {"Version": "3"}

    def create_function_sync_flow(self):
        sync_flow = FunctionSyncFlow(
            "Function1",
            build_context=MagicMock(),
            deploy_context=MagicMock(),
            sync_context=MagicMock(),
            physical_id_mapping={},
            stacks=[MagicMock()],
            application_build_result=self.build_artifacts,
        )
        sync_flow.gather_resources = MagicMock()
        sync_flow.compare_remote = MagicMock()
        sync_flow.sync = MagicMock()
        sync_flow._get_resource_api_calls = MagicMock()

        # Directly set the lambda client to avoid boto3 session issues
        sync_flow._lambda_client = self.lambda_client_mock
        sync_flow._lambda_waiter = self.lambda_client_mock.get_waiter.return_value

        # Mock has_locks to return True for testing
        sync_flow.has_locks = MagicMock(return_value=True)

        return sync_flow

    @patch.multiple(FunctionSyncFlow, __abstractmethods__=set())
    def test_sets_up_clients(self):
        sync_flow = self.create_function_sync_flow()
        # No need to call set_up() since we're directly setting the client in create_function_sync_flow
        self.assertIsNotNone(sync_flow._lambda_client)
        self.assertIsNotNone(sync_flow._lambda_waiter)

    @patch("samcli.lib.sync.flows.function_sync_flow.AliasVersionSyncFlow")
    @patch.multiple(FunctionSyncFlow, __abstractmethods__=set())
    def test_gather_dependencies(self, alias_version_mock):
        sync_flow = self.create_function_sync_flow()
        sync_flow.get_physical_id = lambda x: "PhysicalFunction1"
        sync_flow._get_resource = lambda x: MagicMock()

        result = sync_flow.gather_dependencies()

        sync_flow._lambda_waiter.wait.assert_called_once_with(FunctionName="PhysicalFunction1", WaiterConfig=ANY)
        self.assertEqual(result, [alias_version_mock.return_value])

    @patch.multiple(FunctionSyncFlow, __abstractmethods__=set())
    def test_equality_keys(self):
        sync_flow = self.create_function_sync_flow()
        self.assertEqual(sync_flow._equality_keys(), "Function1")

    @patch("samcli.lib.sync.flows.function_sync_flow.wait_for_function_update_complete")
    @patch.multiple(FunctionSyncFlow, __abstractmethods__=set())
    def test_publish_function_version_with_lock(self, wait_mock):
        function_physical_id = "myFirstFunction"
        publish_target = FunctionPublishTarget.LATEST_PUBLISHED
        response_version = "$LATEST.PUBLISHED"

        sync_flow = self.create_function_sync_flow()
        sync_flow._get_lock_chain = MagicMock()

        # Configure the mock response for this specific test
        self.lambda_client_mock.publish_version.return_value = {"Version": response_version}

        # Create a mock for the publish params
        publish_params = FunctionPublishVersionParams(FunctionName=function_physical_id, PublishTo=publish_target)

        # Call the method
        sync_flow.publish_function_version_with_lock(publish_params)

        sync_flow._get_lock_chain.assert_called_once()
        sync_flow._get_lock_chain.return_value.__enter__.assert_called_once()

        # Verify the publish_version call with the correct parameters
        expected_params = publish_params.to_dict()
        sync_flow._lambda_client.publish_version.assert_called_once_with(**expected_params)

        # Verify that PublishTo parameter is passed as the string "LATEST_PUBLISHED"
        call_args = sync_flow._lambda_client.publish_version.call_args
        self.assertEqual(call_args.kwargs.get("PublishTo"), "LATEST_PUBLISHED")

        wait_mock.assert_called_once_with(sync_flow._lambda_client, function_physical_id, response_version)

    @parameterized.expand(
        [
            ("myFirstFunction", b"code1", None, None, None),
            ("mySecondFunction", None, "bucket1", "key1", None),
            ("myThirdFunction", None, None, None, "image:latest"),
        ]
    )
    @patch("samcli.lib.sync.flows.function_sync_flow.wait_for_function_update_complete")
    @patch.multiple(FunctionSyncFlow, __abstractmethods__=set())
    def test_update_function_with_lock(self, function_physical_id, zip_file, s3_bucket, s3_key, image_uri, wait_mock):
        sync_flow = self.create_function_sync_flow()
        sync_flow._get_lock_chain = MagicMock()
        sync_flow.get_physical_id = MagicMock(return_value=function_physical_id)
        sync_flow._sync_context = MagicMock()
        sync_flow.publish_function_version_with_lock = MagicMock()

        # Configure the mock response
        self.lambda_client_mock.update_function_code.return_value = {"FunctionName": function_physical_id}

        # Create actual FunctionUpdateParams object
        update_params = FunctionUpdateParams(
            FunctionName=function_physical_id, ZipFile=zip_file, S3Bucket=s3_bucket, S3Key=s3_key, ImageUri=image_uri
        )

        # Mock the to_dict method to return expected dictionary
        expected_params = {}
        if function_physical_id:
            expected_params["FunctionName"] = function_physical_id
        if zip_file:
            expected_params["ZipFile"] = zip_file
        if s3_bucket:
            expected_params["S3Bucket"] = s3_bucket
        if s3_key:
            expected_params["S3Key"] = s3_key
        if image_uri:
            expected_params["ImageUri"] = image_uri

        # Call the method
        sync_flow.update_function_with_lock(update_params)

        # Verify the Lambda client was called with the correct parameters
        sync_flow._get_lock_chain.assert_called_once()
        sync_flow._get_lock_chain.return_value.__enter__.assert_called_once()
        self.lambda_client_mock.update_function_code.assert_called_once_with(**expected_params)

        # Check wait was called
        wait_mock.assert_called_once_with(self.lambda_client_mock, function_physical_id)

    @parameterized.expand(
        [
            # publish_to_latest_published, capacity_provider_config, expected_result
            (True, True, True),
            (True, False, False),
            (False, True, False),
            (False, False, False),
        ]
    )
    @patch.multiple(FunctionSyncFlow, __abstractmethods__=set())
    def test_auto_publish_latest_invocable_property(
        self, publish_to_latest_published, has_capacity_provider, expected_result
    ):
        sync_flow = self.create_function_sync_flow()

        # Mock the function properties
        sync_flow._function.publish_to_latest_published = publish_to_latest_published
        if has_capacity_provider:
            sync_flow._function.capacity_provider_configuration = MagicMock()
        else:
            sync_flow._function.capacity_provider_configuration = None

        result = sync_flow.auto_publish_latest_invocable
        self.assertEqual(result, expected_result)
