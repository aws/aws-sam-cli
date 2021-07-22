from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.commands.check.lib.save_data import SaveGraphData, get_config_ctx


class TestSaveData(TestCase):
    def test_generate_resource_toml(self):
        save_data = SaveGraphData(Mock())

        name_mock = Mock()
        duration_mock = Mock()
        tps_mock = Mock()
        resource_children = []

        resource_mock = Mock()
        resource_mock.get_resource_type.return_value = "AWS::Lambda::Function"
        resource_mock.get_name.return_value = name_mock
        resource_mock.get_duration.return_value = duration_mock
        resource_mock.get_tps.return_value = tps_mock
        resource_mock.get_children.return_value = resource_children

        resource_type_mock = resource_mock.get_resource_type.return_value
        resource_name_mock = resource_mock.get_name.return_value
        resource_toml = {
            "resource_object": "",
            "resource_type": resource_type_mock,
            "resource_name": resource_name_mock,
            "duration": duration_mock,
            "tps": tps_mock,
            "children": resource_children,
        }

        # testing lambda function
        result = save_data.generate_resource_toml(resource_mock)

        resource_mock.get_resource_type.assert_called()
        resource_mock.get_name.assert_called()
        resource_mock.get_duration.assert_called()
        resource_mock.get_tps.assert_called()
        resource_mock.get_children.assert_called()

        self.assertEqual(result, resource_toml)

        # testing api gateways
        resource_mock.get_resource_type.return_value = "AWS::ApiGateway::RestApi"
        resource_type_mock = resource_mock.get_resource_type.return_value
        resource_toml = {
            "resource_object": "",
            "resource_type": resource_type_mock,
            "resource_name": resource_name_mock,
            "tps": tps_mock,
            "children": resource_children,
        }

        result = save_data.generate_resource_toml(resource_mock)

        resource_mock.get_resource_type.assert_called()
        resource_mock.get_name.assert_called()
        resource_mock.get_tps.assert_called()
        resource_mock.get_children.assert_called()

        self.assertEqual(result, resource_toml)

        # testing Dynamodb tables
        resource_mock.get_resource_type.return_value = "AWS::DynamoDB::Table"
        resource_type_mock = resource_mock.get_resource_type.return_value
        resource_toml = {
            "resource_object": "",
            "resource_type": resource_type_mock,
            "resource_name": resource_name_mock,
            "tps": tps_mock,
            "children": resource_children,
        }

        result = save_data.generate_resource_toml(resource_mock)

        resource_mock.get_resource_type.assert_called()
        resource_mock.get_name.assert_called()
        resource_mock.get_tps.assert_called()
        resource_mock.get_children.assert_called()

        self.assertEqual(result, resource_toml)

    def test_parse_resources(self):
        resource_toml_mock = Mock()
        name_mock = Mock()

        resource_mock = Mock()
        resource_mock.get_name.return_value = name_mock

        resources = [resource_mock]
        resources_to_analyze_toml = {}

        save_data = SaveGraphData(Mock())
        save_data.generate_resource_toml = Mock()
        save_data.generate_resource_toml.return_value = resource_toml_mock

        save_data.parse_resources(resources, resources_to_analyze_toml)

        save_data.generate_resource_toml.assert_called_once_with(resource_mock)

        self.assertEqual(resources_to_analyze_toml[name_mock], resource_toml_mock)

    def test_get_lambda_function_pricing_info(self):
        requests_mock = Mock()
        duration_mock = Mock()
        memory_mock = Mock()
        memory_unit_mock = Mock()

        lambda_pricing_info_mock = Mock()
        lambda_pricing_info_mock.get_number_of_requests.return_value = requests_mock
        lambda_pricing_info_mock.get_average_duration.return_value = duration_mock
        lambda_pricing_info_mock.get_allocated_memory.return_value = memory_mock
        lambda_pricing_info_mock.get_allocated_memory_unit.return_value = memory_unit_mock

        graph_mock = Mock()
        graph_mock.get_lambda_function_pricing_info.return_value = lambda_pricing_info_mock

        save_data = SaveGraphData(graph_mock)
        result = save_data.get_lambda_function_pricing_info()

        expected_result = {
            "number_of_requests": requests_mock,
            "average_duration": duration_mock,
            "allocated_memory": memory_mock,
            "allocated_memory_unit": memory_unit_mock,
        }

        self.assertEqual(result, expected_result)

    @patch("samcli.commands.check.lib.save_data.get_config_ctx")
    def test_save_to_config_file(self, patch_get_config_ctx):
        samconfig_mock = Mock()
        samconfig_mock.put = Mock()
        samconfig_mock.flush = Mock()

        config_file_mock = Mock()

        patch_get_config_ctx.return_value = samconfig_mock

        resources_mock = Mock()
        lambda_function_pricing_info_toml_mock = Mock()

        graph_mock = Mock()
        graph_mock.get_entry_points.return_value = resources_mock

        resources_to_analyze_toml = {}

        save_data = SaveGraphData(graph_mock)
        save_data.parse_resources = Mock()
        save_data.get_lambda_function_pricing_info = Mock()
        save_data.get_lambda_function_pricing_info.return_value = lambda_function_pricing_info_toml_mock

        graph_dict = {
            "resources_to_analyze": resources_to_analyze_toml,
            "lambda_function_pricing_info": lambda_function_pricing_info_toml_mock,
        }

        save_data.save_to_config_file(config_file_mock)

        patch_get_config_ctx.assert_called_once_with(config_file_mock)
        graph_mock.get_entry_points.assert_called_once()
        save_data.parse_resources.assert_called_once_with(resources_mock, resources_to_analyze_toml)
        save_data.get_lambda_function_pricing_info.assert_called_once()
        samconfig_mock.put.assert_called_once_with(["load"], "graph", "all_graph_data", graph_dict, "check")
        samconfig_mock.flush.assert_called_once()

    @patch("samcli.commands.check.lib.save_data.getattr")
    @patch("samcli.commands.check.lib.save_data.SamConfig")
    @patch("samcli.commands.check.lib.save_data.click")
    @patch("samcli.commands.check.lib.save_data.os")
    def test_get_config_ctx(self, patch_os, patch_click, patch_samconfig, patch_getattr):
        path_mock = Mock()
        ctx_mock = Mock()
        samconfig_mock = Mock()
        config_file_mock = Mock()
        samconfig_dir_mock = Mock()

        patch_os.path.realpath.return_value = path_mock
        patch_click.get_current_context.return_value = ctx_mock
        patch_getattr.return_value = samconfig_dir_mock
        patch_samconfig.return_value = samconfig_mock

        result = get_config_ctx(config_file_mock)

        patch_getattr.assert_called_once_with(ctx_mock, "samconfig_dir", None)
        patch_samconfig.assert_called_once_with(config_dir=samconfig_dir_mock, filename=config_file_mock)
        self.assertEqual(result, samconfig_mock)
