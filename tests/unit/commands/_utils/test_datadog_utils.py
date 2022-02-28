from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.lib.utils.resources import AWS_LAMBDA_FUNCTION, AWS_APIGATEWAY_RESTAPI

from samcli.commands.logs.command import cli

import sys

from io import StringIO

from samcli.commands._utils.datadog_utils import generate_datadog_url

class TestDatadogUtils(TestCase):

    def test_generate_datadog_url_multiple_lambda_resources(self):
        mock_resource_info_list = [
            Mock(resource_type=AWS_LAMBDA_FUNCTION, physical_resource_id="func1_123" , logical_resource_id="func1"),
            Mock(resource_type=AWS_APIGATEWAY_RESTAPI, physical_resource_id="not_a_functions1_123" , logical_resource_id="not_a_function1"),
            Mock(resource_type=AWS_LAMBDA_FUNCTION, physical_resource_id="func2_123" , logical_resource_id="func2"),
            Mock(resource_type=AWS_APIGATEWAY_RESTAPI, physical_resource_id="not_a_functions2_123" , logical_resource_id="not_a_function2"),
            Mock(resource_type=AWS_LAMBDA_FUNCTION, physical_resource_id="func3_123" , logical_resource_id="func3"),
        ]

        expected_output = ("If your functions are instrumented with Datadog, use the following links to see datadog live tailed logs:\n"
                           "func1: https://app.datadoghq.com/logs/livetail?query=functionname%3Afunc1_123\n"
                           "func2: https://app.datadoghq.com/logs/livetail?query=functionname%3Afunc2_123\n"
                           "func3: https://app.datadoghq.com/logs/livetail?query=functionname%3Afunc3_123")

        with patch('sys.stdout', new=StringIO()) as output:
            generate_datadog_url(mock_resource_info_list)
            self.assertEqual(expected_output, output.getvalue().strip())

    def test_generate_datadog_url_one_lambda_resource(self):
        mock_resource_info_list = [
            Mock(resource_type=AWS_APIGATEWAY_RESTAPI, physical_resource_id="not_a_functions1_123" , logical_resource_id="not_a_function1"),
            Mock(resource_type=AWS_LAMBDA_FUNCTION, physical_resource_id="func1_123" , logical_resource_id="func1"),
            Mock(resource_type=AWS_APIGATEWAY_RESTAPI, physical_resource_id="not_a_functions2_123" , logical_resource_id="not_a_function2"),
        ]

        expected_output = ("If your functions are instrumented with Datadog, use the following links to see datadog live tailed logs:\n"
                           "func1: https://app.datadoghq.com/logs/livetail?query=functionname%3Afunc1_123")
        
        with patch('sys.stdout', new=StringIO()) as output:
            generate_datadog_url(mock_resource_info_list)
            self.assertEqual(expected_output, output.getvalue().strip())

    def test_generate_datadog_url_no_lambda_functions(self):
        mock_resource_info_list = [
            Mock(resource_type=AWS_APIGATEWAY_RESTAPI, physical_resource_id="not_a_functions1_123" , logical_resource_id="not_a_function1"),
        ]

        expected_output = "There are no lambda functions in your stack."
        
        with patch('sys.stdout', new=StringIO()) as output:
            generate_datadog_url(mock_resource_info_list)
            self.assertEqual(expected_output, output.getvalue().strip())