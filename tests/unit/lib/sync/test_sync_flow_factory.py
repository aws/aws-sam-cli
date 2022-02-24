from unittest import TestCase
from unittest.mock import MagicMock, patch, Mock

from samcli.lib.sync.sync_flow_factory import SyncFlowFactory


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
            stacks=[stack_resource, MagicMock()],
            auto_dependency_layer=auto_dependency_layer,
        )
        return factory

    @patch("samcli.lib.sync.sync_flow_factory.get_physical_id_mapping")
    @patch("samcli.lib.sync.sync_flow_factory.get_boto_resource_provider_with_config")
    def test_load_physical_id_mapping(self, get_boto_resource_provider_mock, get_physical_id_mapping_mock):
        get_physical_id_mapping_mock.return_value = {"Resource1": "PhysicalResource1", "Resource2": "PhysicalResource2"}

        factory = self.create_factory()
        factory.load_physical_id_mapping()

        self.assertEqual(len(factory._physical_id_mapping), 3)
        self.assertEqual(
            factory._physical_id_mapping,
            {"Resource1": "PhysicalResource1", "Resource2": "PhysicalResource2", "CDKResource2": "PhysicalResource2"},
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
        result = factory._create_layer_flow("Layer1", {})
        self.assertEqual(result, layer_sync_mock.return_value)

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
