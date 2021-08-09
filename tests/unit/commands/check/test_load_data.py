from unittest import TestCase, load_tests
from unittest.mock import MagicMock, Mock, patch

from samcli.commands.check.lib.load_data import (
    LoadData,
    _check_pricing_info,
    _check_range,
    _get_data_from_toml,
    _generate_lambda_function,
    _generate_api_gateway,
    _generate_dynamo_db_table,
)


class TestLoadData(TestCase):
    @patch("samcli.commands.check.lib.load_data.get_config_ctx")
    def test_get_data_from_toml(self, patch_get_config_ctx):

        config_file_mock = Mock()
        result_mock = Mock()
        samconfig_mock = Mock()
        samconfig_mock.get_all = Mock()
        samconfig_mock.get_all.return_value = {"all_graph_data": result_mock}

        patch_get_config_ctx.return_value = samconfig_mock

        result = _get_data_from_toml(config_file_mock)

        patch_get_config_ctx.assert_called_once_with(config_file_mock)
        samconfig_mock.get_all.assert_called_once_with(["load"], "graph", "check")

        self.assertEqual(result, result_mock)

    @patch("samcli.commands.check.lib.load_data._check_pricing_info")
    @patch("samcli.commands.check.lib.load_data.CheckGraph")
    @patch("samcli.commands.check.lib.load_data.LambdaFunctionPricing")
    def test_parse_toml_lambda_function_info(self, patch_lambda_function_pricing, patch_graph, patch_pricing_info):
        graph_mock = Mock()
        graph_mock.unique_pricing_info = {}
        patch_graph.return_value = graph_mock

        toml_lambda_function_info_mock = MagicMock()

        load_data = LoadData()
        load_data._graph_toml = {"lambda_function_pricing_info": toml_lambda_function_info_mock}

        lambda_function_pricing_mock = Mock()
        patch_lambda_function_pricing.return_value = lambda_function_pricing_mock

        load_data._parse_toml_lambda_function_info()

        patch_lambda_function_pricing.assert_called_once()

        patch_pricing_info.assert_called_once_with(lambda_function_pricing_mock)

    @patch("samcli.commands.check.lib.load_data.CheckGraph")
    def test_parse_resources(self, patch_graph):
        resource_toml_mock = Mock()
        resources_toml_mock = Mock()
        resources_toml_mock.values.return_value = [resource_toml_mock]

        graph_mock = Mock()
        graph_mock.set_lambda_function_pricing_info = Mock()
        patch_graph.return_value = graph_mock

        load_data = LoadData()
        load_data._parse_single_resource_toml = Mock()

        load_data._graph_toml = {"resources_to_analyze": resources_toml_mock}

        load_data._parse_resources()

        resources_toml_mock.values.assert_called_once()
        load_data._parse_single_resource_toml.assert_called_once_with(resource_toml_mock)

    @patch("samcli.commands.check.lib.load_data._generate_dynamo_db_table")
    @patch("samcli.commands.check.lib.load_data._generate_api_gateway")
    @patch("samcli.commands.check.lib.load_data._generate_lambda_function")
    @patch("samcli.commands.check.lib.load_data._check_range")
    @patch("samcli.commands.check.lib.load_data.CheckGraph")
    def test_parse_single_resource_toml(self, patch_graph, patch_range, patch_lambda, patch_api, patch_dynamo):
        resource_name = ""
        resource_object = ""
        tps = 0
        duration = 0
        is_entry_point = False
        path_to_resource = Mock()

        current_resource_mock = Mock()
        children = []

        graph_mock = Mock()
        graph_mock.resources_to_analyze = {}
        patch_graph.return_value = graph_mock

        load_data = LoadData()
        patch_lambda.return_value = current_resource_mock
        patch_api.return_value = current_resource_mock
        patch_dynamo.return_value = current_resource_mock

        # testing lambda functions
        resource_type = "AWS::Lambda::Function"
        resource_toml = {
            "resource_type": resource_type,
            "resource_name": resource_name,
            "resource_object": resource_object,
            "children": children,
            "tps": tps,
            "duration": duration,
            "key": "",
            "path_to_resource": path_to_resource,
        }

        result = load_data._parse_single_resource_toml(resource_toml, is_entry_point)

        self.assertEqual(result, current_resource_mock)

        # testing api gateways
        resource_type = "AWS::ApiGateway::RestApi"
        resource_toml = {
            "resource_type": resource_type,
            "resource_name": resource_name,
            "resource_object": resource_object,
            "children": children,
            "tps": tps,
            "duration": duration,
            "path_to_resource": path_to_resource,
        }

        result = load_data._parse_single_resource_toml(resource_toml, is_entry_point)

        self.assertEqual(result, current_resource_mock)

        # testing api gateways
        resource_type = "AWS::DynamoDB::Table"
        resource_toml = {
            "resource_type": resource_type,
            "resource_name": resource_name,
            "resource_object": resource_object,
            "children": children,
            "tps": tps,
            "duration": duration,
            "path_to_resource": path_to_resource,
        }

        result = load_data._parse_single_resource_toml(resource_toml, is_entry_point)

        self.assertEqual(result, current_resource_mock)

    @patch("samcli.commands.check.lib.load_data.CheckGraph")
    @patch("samcli.commands.check.lib.load_data.LambdaFunction")
    def test_generate_lambda_function(self, patch_lambda_function, patch_graph):
        resource_name_mock = Mock()
        resource_object_mock = Mock()
        tps_mock = Mock()
        duration_mock = Mock()
        resource_type_mock = Mock()
        path_to_resource_mock = Mock()

        lambda_function_mock = Mock()

        patch_lambda_function.return_value = lambda_function_mock

        load_data = LoadData()
        result = _generate_lambda_function(
            resource_type_mock,
            resource_name_mock,
            resource_object_mock,
            tps_mock,
            duration_mock,
            path_to_resource_mock,
        )

        patch_lambda_function.assert_called_once_with(
            resource_object_mock, resource_type_mock, resource_name_mock, path_to_resource_mock
        )

        self.assertEqual(result, lambda_function_mock)

    @patch("samcli.commands.check.lib.load_data.CheckGraph")
    @patch("samcli.commands.check.lib.load_data.ApiGateway")
    def test_generate_api_gateway(self, patch_api_gateway, patch_graph):
        resource_name_mock = Mock()
        resource_object_mock = Mock()
        tps_mock = Mock()
        resource_type_mock = Mock()
        path_to_resource = Mock()

        api_gateway_mock = Mock()

        patch_api_gateway.return_value = api_gateway_mock

        load_data = LoadData()
        result = _generate_api_gateway(
            resource_type_mock,
            resource_name_mock,
            resource_object_mock,
            tps_mock,
            path_to_resource,
        )

        patch_api_gateway.assert_called_once_with(
            resource_object_mock, resource_type_mock, resource_name_mock, path_to_resource
        )

        self.assertEqual(result, api_gateway_mock)

    @patch("samcli.commands.check.lib.load_data.CheckGraph")
    @patch("samcli.commands.check.lib.load_data.DynamoDB")
    def test_generate_dynamodb_table(self, patch_dynamodb_table, patch_graph):
        resource_name_mock = Mock()
        resource_object_mock = Mock()
        tps_mock = Mock()
        resource_type_mock = Mock()
        path_to_resource = Mock()

        dynamodb_table_mock = Mock()

        patch_dynamodb_table.return_value = dynamodb_table_mock

        load_data = LoadData()
        result = _generate_dynamo_db_table(
            resource_type_mock,
            resource_name_mock,
            resource_object_mock,
            tps_mock,
            path_to_resource,
        )

        patch_dynamodb_table.assert_called_once_with(
            resource_object_mock, resource_type_mock, resource_name_mock, path_to_resource
        )

        self.assertEqual(result, dynamodb_table_mock)

    def test_check_range(self):
        value = 0
        min_value = 5
        max_value = 10

        with self.assertRaises(ValueError):
            load_data = LoadData()
            _check_range(value, min_value, max_value)

        value = 42
        min_value = 4
        max_value = 8

        with self.assertRaises(ValueError):
            load_data = LoadData()
            _check_range(value, min_value, max_value)

    @patch("samcli.commands.check.lib.load_data._check_range")
    def test_check_pricing_info(self, patch_range):
        requests_mock = Mock()
        duration_mock = Mock()
        memory_mock = Mock()
        memory_unit = ""

        lambda_function_pricing_mock = Mock()
        lambda_function_pricing_mock.number_of_requests = requests_mock
        lambda_function_pricing_mock.average_duration = duration_mock
        lambda_function_pricing_mock.allocated_memory = memory_mock
        lambda_function_pricing_mock.allocated_memory_unit = memory_unit

        min_memory = 128
        max_memory = 10000
        min_requests = 0
        min_duration = 0
        max_duration = 900000

        load_data = LoadData()

        with self.assertRaises(ValueError):
            _check_pricing_info(lambda_function_pricing_mock)

        memory_unit = "MB"
        lambda_function_pricing_mock.allocated_memory_unit = memory_unit

        _check_pricing_info(lambda_function_pricing_mock)

        patch_range.assert_any_call(requests_mock, min_requests, float("inf"))
        patch_range.assert_any_call(duration_mock, min_duration, max_duration)
        patch_range.assert_any_call(memory_mock, min_memory, max_memory)

    @patch("samcli.commands.check.lib.load_data._get_data_from_toml")
    @patch("samcli.commands.check.lib.load_data.CheckGraph")
    def test_generate_graph_from_toml(self, patch_graph, patch_data):
        import tomlkit.exceptions

        config_file_mock = Mock()
        graph_toml_mock = Mock()
        graph_mock = Mock()

        patch_graph.return_value = graph_mock
        load_data = LoadData()
        load_data._parse_toml_lambda_function_info = Mock()
        load_data._parse_resources = Mock()

        patch_data.return_value = graph_toml_mock

        with self.assertRaises(TypeError):
            load_data._parse_resources.side_effect = TypeError()
            load_data.generate_graph_from_toml(config_file_mock)

        with self.assertRaises(tomlkit.exceptions.NonExistentKey):
            load_data._parse_resources.side_effect = tomlkit.exceptions.NonExistentKey(Mock())
            load_data.generate_graph_from_toml(config_file_mock)

        with self.assertRaises(ValueError):
            load_data._parse_resources.side_effect = ValueError("invalid type")
            load_data.generate_graph_from_toml(config_file_mock)

        with self.assertRaises(ValueError):
            load_data._parse_resources.side_effect = ValueError("invalid number")
            load_data.generate_graph_from_toml(config_file_mock)

        with self.assertRaises(ValueError):
            load_data._parse_resources.side_effect = ValueError("invalid unit")
            load_data.generate_graph_from_toml(config_file_mock)

        load_data._parse_resources.side_effect = None
        result = load_data.generate_graph_from_toml(config_file_mock)

        self.assertEqual(result, graph_mock)
