from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.commands.check.lib.save_data import SaveGraphData, get_config_ctx


class TestSaveData(TestCase):
    def test_generate_lambda_toml(self):
        graph_mock = Mock()

        lambda_function_mock = Mock()
        children_toml_mock = Mock()
        copied_lambda_function_mock = Mock()
        entry_point_resource = ""

        lambda_function_mock.resource_name = ""
        key = lambda_function_mock.resource_name + ":" + entry_point_resource

        graph_mock.resources_to_analyze = {key: copied_lambda_function_mock}

        copied_lambda_function_mock.resource_type = Mock()
        copied_lambda_function_mock.resource_name = Mock()
        copied_lambda_function_mock.duration = Mock()
        copied_lambda_function_mock.tps = Mock()
        copied_lambda_function_mock.path_to_resource = Mock()

        lambda_toml = {
            "resource_object": "",
            "resource_type": copied_lambda_function_mock.resource_type,
            "resource_name": copied_lambda_function_mock.resource_name,
            "duration": copied_lambda_function_mock.duration,
            "tps": copied_lambda_function_mock.tps,
            "children": children_toml_mock,
            "key": key,
            "path_to_resource": copied_lambda_function_mock.path_to_resource,
        }

        save_data = SaveGraphData(graph_mock)
        result = save_data._generate_lambda_toml(lambda_function_mock, children_toml_mock, entry_point_resource)

        self.assertEqual(result, lambda_toml)

    def test_generate_resource_toml(self):
        graph_mock = Mock()
        entry_point_resource = ""
        resource_toml = Mock()

        save_data = SaveGraphData(graph_mock)

        resource_mock = Mock()
        resource_mock.resource_type = "AWS::Lambda::Function"
        resource_mock.reource_name = Mock()
        resource_mock.children = []

        save_data._generate_lambda_toml = Mock()
        save_data._generate_lambda_toml.return_value = resource_toml

        result = save_data._generate_resource_toml(resource_mock, entry_point_resource)

        save_data._generate_lambda_toml.assert_called_once_with(resource_mock, [], entry_point_resource)
        self.assertEqual(result, resource_toml)

    def test_parse_resources(self):
        resource_toml_mock = Mock()
        name = "Name"
        entry_point_resource = "Mock"
        key = name + ":" + entry_point_resource

        resource_mock = Mock()
        resource_mock.resource_name = name
        resource_mock.entry_point_resource = entry_point_resource

        resources = [resource_mock]
        resources_to_analyze_toml = {}

        save_data = SaveGraphData(Mock())
        save_data._generate_resource_toml = Mock()
        save_data._generate_resource_toml.return_value = resource_toml_mock

        save_data._parse_resources(resources, resources_to_analyze_toml)

        save_data._generate_resource_toml.assert_called_once_with(resource_mock, entry_point_resource)

        self.assertEqual(resources_to_analyze_toml[key], resource_toml_mock)

    def test_get_lambda_function_pricing_info(self):
        requests_mock = Mock()
        duration_mock = Mock()
        memory_mock = Mock()
        memory_unit_mock = Mock()

        lambda_pricing_info_mock = Mock()
        lambda_pricing_info_mock.number_of_requests = requests_mock
        lambda_pricing_info_mock.average_duration = duration_mock
        lambda_pricing_info_mock.allocated_memory = memory_mock
        lambda_pricing_info_mock.allocated_memory_unit = memory_unit_mock

        graph_mock = Mock()
        graph_mock.unique_pricing_info = {"LambdaFunction": lambda_pricing_info_mock}

        save_data = SaveGraphData(graph_mock)
        result = save_data._get_lambda_function_pricing_info()

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
        graph_mock.entry_points = resources_mock

        resources_to_analyze_toml = {}

        save_data = SaveGraphData(graph_mock)
        save_data._parse_resources = Mock()
        save_data._get_lambda_function_pricing_info = Mock()
        save_data._get_lambda_function_pricing_info.return_value = lambda_function_pricing_info_toml_mock

        graph_dict = {
            "resources_to_analyze": resources_to_analyze_toml,
            "lambda_function_pricing_info": lambda_function_pricing_info_toml_mock,
        }

        save_data.save_to_config_file(config_file_mock)

        patch_get_config_ctx.assert_called_once_with(config_file_mock)
        save_data._parse_resources.assert_called_once_with(resources_mock, resources_to_analyze_toml)
        save_data._get_lambda_function_pricing_info.assert_called_once()
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
