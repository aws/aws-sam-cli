from unittest import TestCase
from unittest.mock import MagicMock, Mock, patch

from samcli.commands.check.lib.resource_provider import ResourceProvider


class TestResourceProvider(TestCase):
    @patch("samcli.commands.check.lib.resource_provider.os")
    @patch("samcli.commands.check.lib.resource_provider.tempfile")
    @patch("samcli.commands.check.lib.resource_provider.yaml_dump")
    @patch("samcli.commands.check.lib.resource_provider.SamLocalStackProvider")
    def test_get_local_stacks(self, patch_stack, patch_dump, patch_temp, patch_os):
        new_file_mock = Mock()
        path_mock = Mock()
        tmp_mock = Mock()
        local_stacks_mock = Mock()
        template_mock = Mock()

        patch_temp.mkstemp.return_value = [new_file_mock, path_mock]

        patch_os.fdopen = Mock()
        patch_os.fdopen.return_value = tmp_mock
        patch_os.remove = Mock()

        tmp_mock.write = Mock()
        tmp_mock.close = Mock()

        patch_stack.get_stacks.return_value = [[[None, None, None, None, local_stacks_mock]]]

        resource_provider = ResourceProvider(template_mock)

        result = resource_provider.get_local_stacks()

        self.assertEqual(local_stacks_mock, result)

    @patch("samcli.commands.check.lib.resource_provider.ApiGateway")
    @patch("samcli.commands.check.lib.resource_provider.LambdaFunctionPermission")
    @patch("samcli.commands.check.lib.resource_provider.EventSourceMapping")
    @patch("samcli.commands.check.lib.resource_provider.DynamoDB")
    def test_get_all_resources(self, patch_dynamo, patch_map, patch_perm, patch_api):
        resource_provider = ResourceProvider(Mock())

        api_object = {"Type": "AWS::ApiGateway::RestApi"}
        api_name = Mock()
        perm_object = {"Type": "AWS::Lambda::Permission"}
        perm_name = Mock()
        map_object = {"Type": "AWS::Lambda::EventSourceMapping"}
        map_name = Mock()
        dynamo_object = {"Type": "AWS::DynamoDB::Table"}
        dynamo_name = Mock()

        resources_mock = {
            api_name: api_object,
            perm_name: perm_object,
            map_name: map_object,
            dynamo_name: dynamo_object,
        }
        local_stacks_mock = {"Resources": resources_mock}

        resource_provider.get_local_stacks = Mock()
        resource_provider.get_local_stacks.return_value = local_stacks_mock

        resource_provider.get_all_resources()

        patch_dynamo.assert_called_once_with(dynamo_object, dynamo_object["Type"], dynamo_name)
        patch_map.assert_called_once_with(map_object, map_object["Type"], map_name)
        patch_perm.assert_called_once_with(perm_object, perm_object["Type"], perm_name)
        patch_api.assert_called_once_with(api_object, api_object["Type"], api_name)
