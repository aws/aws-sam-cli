from samcli.lib.providers.provider import ResourceIdentifier
from unittest import TestCase
from unittest.mock import ANY, MagicMock, call, patch

from samcli.lib.sync.sync_flow import SyncFlow, ResourceAPICall
from samcli.lib.sync.flows.function_sync_flow import FunctionSyncFlow
from samcli.lib.utils.lock_distributor import LockChain

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

    @patch("samcli.lib.sync.sync_flow_factory.ImageFunctionSyncFlow")
    @patch("samcli.lib.sync.sync_flow_factory.ZipFunctionSyncFlow")
    @patch("samcli.lib.sync.sync_flow_factory.Config")
    def test_create_lambda_flow_other(self, config_mock, zip_function_mock, image_function_mock):
        factory = self.create_factory()
        resource = {"Properties": {"PackageType": "Other"}}
        result = factory._create_lambda_flow("Function1", resource)
        self.assertEqual(result, None)

    @patch("samcli.lib.sync.sync_flow_factory.get_resource_by_id")
    @patch("samcli.lib.sync.sync_flow_factory.Config")
    def test_create_sync_flow_valid(self, config_mock, get_resource_by_id_mock):
        resource = {"Type": "AWS::Lambda::Function"}
        get_resource_by_id_mock.return_value = resource

        factory = self.create_factory()
        create_lambda_flow_mock = MagicMock()
        SyncFlowFactory.FLOW_FACTORY_FUNCTIONS["AWS::Lambda::Function"] = create_lambda_flow_mock
        result = factory.create_sync_flow(ResourceIdentifier("Resource1"))

        create_lambda_flow_mock.assert_called_once_with(factory, "Resource1", resource)
        self.assertEqual(create_lambda_flow_mock.return_value, result)

    @patch("samcli.lib.sync.sync_flow_factory.get_resource_by_id")
    @patch("samcli.lib.sync.sync_flow_factory.Config")
    def test_create_sync_flow_unknown_type(self, config_mock, get_resource_by_id_mock):
        resource = {"Type": "AWS::Unknown::Type"}
        get_resource_by_id_mock.return_value = resource

        factory = self.create_factory()
        result = factory.create_sync_flow(ResourceIdentifier("Resource1"))

        self.assertEqual(None, result)

    @patch("samcli.lib.sync.sync_flow_factory.get_resource_by_id")
    @patch("samcli.lib.sync.sync_flow_factory.Config")
    def test_create_sync_flow_no_type(self, config_mock, get_resource_by_id_mock):
        resource = {"Properties": {}}
        get_resource_by_id_mock.return_value = resource

        factory = self.create_factory()
        result = factory.create_sync_flow(ResourceIdentifier("Resource1"))

        self.assertEqual(None, result)
