from unittest import TestCase
from unittest.mock import ANY, MagicMock, call, patch

from samcli.lib.sync.sync_flow_factory import SyncFlowFactory


class TestSyncFlowFactory(TestCase):
    def create_factory(self):
        factory = SyncFlowFactory(
            build_context=MagicMock(), deploy_context=MagicMock(), stacks=[MagicMock(), MagicMock()]
        )
        return factory

    @patch("samcli.lib.sync.sync_flow_factory.boto3.resource")
    @patch("samcli.lib.sync.sync_flow_factory.Config")
    def test_load_physical_id_mapping(self, config_mock, resource_mock):
        resource1 = MagicMock()
        resource1.logical_resource_id = "Resource1"
        resource1.physical_resource_id = "PhysicalResource1"
        resource2 = MagicMock()
        resource2.logical_resource_id = "Resource2"
        resource2.physical_resource_id = "PhysicalResource2"

        stack_mock = MagicMock()
        stack_mock.resource_summaries.all.return_value = [resource1, resource2]
        resource_mock.return_value.Stack.return_value = stack_mock

        factory = self.create_factory()
        factory.load_physical_id_mapping()

        self.assertEqual(len(factory._physical_id_mapping), 2)
        self.assertEqual(
            factory._physical_id_mapping, {"Resource1": "PhysicalResource1", "Resource2": "PhysicalResource2"}
        )

    @patch("samcli.lib.sync.sync_flow_factory.ImageFunctionSyncFlow")
    @patch("samcli.lib.sync.sync_flow_factory.ZipFunctionSyncFlow")
    @patch("samcli.lib.sync.sync_flow_factory.Config")
    def test_create_lambda_flow_zip(self, config_mock, zip_function_mock, image_function_mock):
        factory = self.create_factory()
        resource = {"Properties": {"PackageType": "Zip"}}
        result = factory._create_lambda_flow("Function1", resource)
        self.assertEqual(result, zip_function_mock.return_value)

    @patch("samcli.lib.sync.sync_flow_factory.ImageFunctionSyncFlow")
    @patch("samcli.lib.sync.sync_flow_factory.ZipFunctionSyncFlow")
    @patch("samcli.lib.sync.sync_flow_factory.Config")
    def test_create_lambda_flow_image(self, config_mock, zip_function_mock, image_function_mock):
        factory = self.create_factory()
        resource = {"Properties": {"PackageType": "Image"}}
        result = factory._create_lambda_flow("Function1", resource)
        self.assertEqual(result, image_function_mock.return_value)

    @patch("samcli.lib.sync.sync_flow_factory.LayerSyncFlow")
    @patch("samcli.lib.sync.sync_flow_factory.Config")
    def test_create_layer_flow(self, config_mock, layer_sync_mock):
        factory = self.create_factory()
        result = factory._create_layer_flow("Layer1", {})
        self.assertEqual(result, layer_sync_mock.return_value)

    @patch("samcli.lib.sync.sync_flow_factory.ImageFunctionSyncFlow")
    @patch("samcli.lib.sync.sync_flow_factory.ZipFunctionSyncFlow")
    @patch("samcli.lib.sync.sync_flow_factory.Config")
    def test_create_lambda_flow_other(self, config_mock, zip_function_mock, image_function_mock):
        factory = self.create_factory()
        resource = {"Properties": {"PackageType": "Other"}}
        result = factory._create_lambda_flow("Function1", resource)
        self.assertEqual(result, None)

    @patch("samcli.lib.sync.sync_flow_factory.RestApiSyncFlow")
    @patch("samcli.lib.sync.sync_flow_factory.Config")
    def test_create_rest_api_flow(self, config_mock, rest_api_sync_mock):
        factory = self.create_factory()
        result = factory._create_rest_api_flow("API1", {})
        self.assertEqual(result, rest_api_sync_mock.return_value)

    @patch("samcli.lib.sync.sync_flow_factory.HttpApiSyncFlow")
    @patch("samcli.lib.sync.sync_flow_factory.Config")
    def test_create_api_flow(self, config_mock, http_api_sync_mock):
        factory = self.create_factory()
        result = factory._create_api_flow("API1", {})
        self.assertEqual(result, http_api_sync_mock.return_value)

    @patch("samcli.lib.sync.sync_flow_factory.get_resource_by_id")
    @patch("samcli.lib.sync.sync_flow_factory.Config")
    def test_create_sync_flow(self, config_mock, get_resource_by_id_mock):
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
