from unittest import TestCase
from unittest.mock import MagicMock, patch, Mock

from parameterized import parameterized

from samcli.lib.sync.sync_flow_factory import SyncCodeResources, SyncFlowFactory
from samcli.lib.utils.cloudformation import CloudFormationResourceSummary
from samcli.lib.utils.resources import (
    AWS_SERVERLESS_FUNCTION,
    AWS_LAMBDA_FUNCTION,
    AWS_SERVERLESS_LAYERVERSION,
    AWS_LAMBDA_LAYERVERSION,
    AWS_SERVERLESS_API,
    AWS_APIGATEWAY_RESTAPI,
    AWS_SERVERLESS_HTTPAPI,
    AWS_APIGATEWAY_V2_API,
    AWS_SERVERLESS_STATEMACHINE,
    AWS_STEPFUNCTIONS_STATEMACHINE,
)


class TestSyncFlowFactory(TestCase):
    def create_factory(self, auto_dependency_layer: bool = False):
        stack_resource = MagicMock()
        stack_resource.resources = {
            "Resource1": {
                "Type": "TypeA",
                "Properties": {"Body1"},
            },
            "Resource2": {
                "Type": "TypeB",
                "Properties": {"Body2"},
                "Metadata": {
                    "SamResourceId": "CDKResource2",
                },
            },
        }
        factory = SyncFlowFactory(
            build_context=MagicMock(),
            deploy_context=MagicMock(),
            sync_context=MagicMock(),
            stacks=[stack_resource, MagicMock()],
            auto_dependency_layer=auto_dependency_layer,
        )
        return factory

    @patch("samcli.lib.sync.sync_flow_factory.get_resource_summaries")
    @patch("samcli.lib.sync.sync_flow_factory.get_boto_resource_provider_with_config")
    @patch("samcli.lib.sync.sync_flow_factory.get_boto_client_provider_with_config")
    def test_load_physical_id_mapping(
        self, get_boto_client_provider_mock, get_boto_resource_provider_mock, get_resource_summaries_mock
    ):
        resource_summary_1 = CloudFormationResourceSummary(
            resource_type="", logical_resource_id="", physical_resource_id="PhysicalResource1"
        )
        resource_summary_2 = CloudFormationResourceSummary(
            resource_type="", logical_resource_id="", physical_resource_id="PhysicalResource2"
        )
        # get_resource_summaries_mock.return_value = {"Resource1": "PhysicalResource1", "Resource2": "PhysicalResource2"}
        get_resource_summaries_mock.return_value = {"Resource1": resource_summary_1, "Resource2": resource_summary_2}
        factory = self.create_factory()
        factory.load_physical_id_mapping()

        self.assertEqual(len(factory._physical_id_mapping), 2)
        self.assertEqual(
            factory._physical_id_mapping,
            {"Resource1": "PhysicalResource1", "Resource2": "PhysicalResource2"},
        )

    @patch("samcli.lib.sync.sync_flow_factory.ImageFunctionSyncFlow")
    @patch("samcli.lib.sync.sync_flow_factory.ZipFunctionSyncFlow")
    def test_create_lambda_flow_zip(self, zip_function_mock, image_function_mock):
        factory = self.create_factory()
        resource = {"Properties": {"PackageType": "Zip"}}
        result = factory._create_lambda_flow("Function1", resource)
        self.assertEqual(result, zip_function_mock.return_value)

    @patch("samcli.lib.sync.sync_flow_factory.ImageFunctionSyncFlow")
    @patch("samcli.lib.sync.sync_flow_factory.ZipFunctionSyncFlow")
    @patch("samcli.lib.sync.sync_flow_factory.AutoDependencyLayerParentSyncFlow")
    def test_create_lambda_flow_zip_with_auto_dependency_layer(
        self, auto_dependency_layer_mock, zip_function_mock, image_function_mock
    ):
        factory = self.create_factory(True)
        resource = {"Properties": {"PackageType": "Zip", "Runtime": "python3.8"}}
        result = factory._create_lambda_flow("Function1", resource)
        self.assertEqual(result, auto_dependency_layer_mock.return_value)

    @patch("samcli.lib.sync.sync_flow_factory.ImageFunctionSyncFlow")
    @patch("samcli.lib.sync.sync_flow_factory.ZipFunctionSyncFlow")
    @patch("samcli.lib.sync.sync_flow_factory.AutoDependencyLayerParentSyncFlow")
    def test_create_lambda_flow_zip_with_unsupported_runtime_auto_dependency_layer(
        self, auto_dependency_layer_mock, zip_function_mock, image_function_mock
    ):
        factory = self.create_factory(True)
        resource = {"Properties": {"PackageType": "Zip", "Runtime": "ruby2.7"}}
        result = factory._create_lambda_flow("Function1", resource)
        self.assertEqual(result, zip_function_mock.return_value)

    @patch("samcli.lib.sync.sync_flow_factory.ImageFunctionSyncFlow")
    @patch("samcli.lib.sync.sync_flow_factory.ZipFunctionSyncFlow")
    def test_create_lambda_flow_image(self, zip_function_mock, image_function_mock):
        factory = self.create_factory()
        resource = {"Properties": {"PackageType": "Image"}}
        result = factory._create_lambda_flow("Function1", resource)
        self.assertEqual(result, image_function_mock.return_value)

    @patch("samcli.lib.sync.sync_flow_factory.LayerSyncFlow")
    def test_create_layer_flow(self, layer_sync_mock):
        factory = self.create_factory()
        # mock layer for not having SkipBuild:True
        factory._build_context.layer_provider.get.return_value = Mock(skip_build=False)
        result = factory._create_layer_flow("Layer1", {})
        self.assertEqual(result, layer_sync_mock.return_value)

    @parameterized.expand([(Mock(build_method=None),), (Mock(skip_build=True),)])
    @patch("samcli.lib.sync.sync_flow_factory.LayerSyncFlowSkipBuildDirectory")
    @patch("samcli.lib.sync.sync_flow_factory.is_local_folder")
    def test_create_layer_flow_with_skip_build_directory(self, layer_mock, is_local_folder_mock, layer_sync_mock):
        factory = self.create_factory()
        # mock layer return to have no build method
        factory._build_context.layer_provider.get.return_value = layer_mock
        # codeuri should resolve as directory
        is_local_folder_mock.return_value = True
        result = factory._create_layer_flow("Layer1", {})
        self.assertEqual(result, layer_sync_mock.return_value)

    @parameterized.expand([(Mock(build_method=None),), (Mock(skip_build=True),)])
    @patch("samcli.lib.sync.sync_flow_factory.LayerSyncFlowSkipBuildZipFile")
    @patch("samcli.lib.sync.sync_flow_factory.is_local_folder")
    @patch("samcli.lib.sync.sync_flow_factory.is_zip_file")
    def test_create_layer_flow_with_skip_build_zip(
        self, layer_mock, is_zip_file_mock, is_local_folder_mock, layer_sync_mock
    ):
        factory = self.create_factory()
        factory._build_context.layer_provider.get.return_value = layer_mock
        # codeuri should resolve as zip file
        is_local_folder_mock.return_value = False
        is_zip_file_mock.return_value = True
        result = factory._create_layer_flow("Layer1", {})
        self.assertEqual(result, layer_sync_mock.return_value)

    def test_create_layer_flow_with_no_layer(self):
        factory = self.create_factory()
        factory._build_context.layer_provider.get.return_value = None
        result = factory._create_layer_flow("Layer1", {})
        self.assertIsNone(result)

    @patch("samcli.lib.sync.sync_flow_factory.ImageFunctionSyncFlow")
    @patch("samcli.lib.sync.sync_flow_factory.ZipFunctionSyncFlow")
    def test_create_lambda_flow_other(self, zip_function_mock, image_function_mock):
        factory = self.create_factory()
        resource = {"Properties": {"PackageType": "Other"}}
        result = factory._create_lambda_flow("Function1", resource)
        self.assertEqual(result, None)

    @patch("samcli.lib.sync.sync_flow_factory.RestApiSyncFlow")
    def test_create_rest_api_flow(self, rest_api_sync_mock):
        factory = self.create_factory()
        result = factory._create_rest_api_flow("API1", {})
        self.assertEqual(result, rest_api_sync_mock.return_value)

    @patch("samcli.lib.sync.sync_flow_factory.HttpApiSyncFlow")
    def test_create_api_flow(self, http_api_sync_mock):
        factory = self.create_factory()
        result = factory._create_api_flow("API1", {})
        self.assertEqual(result, http_api_sync_mock.return_value)

    @patch("samcli.lib.sync.sync_flow_factory.StepFunctionsSyncFlow")
    def test_create_stepfunctions_flow(self, stepfunctions_sync_mock):
        factory = self.create_factory()
        result = factory._create_stepfunctions_flow("StateMachine1", {})
        self.assertEqual(result, stepfunctions_sync_mock.return_value)

    @patch("samcli.lib.sync.sync_flow_factory.get_resource_by_id")
    def test_create_sync_flow(self, get_resource_by_id_mock):
        factory = self.create_factory()

        sync_flow = MagicMock()
        resource_identifier = MagicMock()
        get_resource_by_id = MagicMock()
        get_resource_by_id_mock.return_value = get_resource_by_id
        generator_mock = MagicMock()
        generator_mock.return_value = sync_flow

        get_generator_function_mock = MagicMock()
        get_generator_function_mock.return_value = generator_mock
        factory._get_generator_function = get_generator_function_mock

        result = factory.create_sync_flow(resource_identifier)

        self.assertEqual(result, sync_flow)
        generator_mock.assert_called_once_with(factory, resource_identifier, get_resource_by_id)

    @patch("samcli.lib.sync.sync_flow_factory.get_resource_by_id")
    def test_create_unknown_resource_sync_flow(self, get_resource_by_id_mock):
        get_resource_by_id_mock.return_value = None
        factory = self.create_factory()
        self.assertIsNone(factory.create_sync_flow(MagicMock()))

    @patch("samcli.lib.sync.sync_flow_factory.get_resource_by_id")
    def test_create_none_generator_sync_flow(self, get_resource_by_id_mock):
        factory = self.create_factory()

        resource_identifier = MagicMock()
        get_resource_by_id = MagicMock()
        get_resource_by_id_mock.return_value = get_resource_by_id

        get_generator_function_mock = MagicMock()
        get_generator_function_mock.return_value = None
        factory._get_generator_function = get_generator_function_mock

        self.assertIsNone(factory.create_sync_flow(resource_identifier))


class TestSyncCodeResources(TestCase):
    def test_values(self):
        output = SyncCodeResources.values()
        expected = [
            AWS_SERVERLESS_FUNCTION,
            AWS_LAMBDA_FUNCTION,
            AWS_SERVERLESS_LAYERVERSION,
            AWS_LAMBDA_LAYERVERSION,
            AWS_SERVERLESS_API,
            AWS_APIGATEWAY_RESTAPI,
            AWS_SERVERLESS_HTTPAPI,
            AWS_APIGATEWAY_V2_API,
            AWS_SERVERLESS_STATEMACHINE,
            AWS_STEPFUNCTIONS_STATEMACHINE,
        ]
        self.assertEqual(expected, output)
