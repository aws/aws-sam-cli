from unittest import TestCase
from unittest.mock import patch, MagicMock
from yaml.parser import ParserError

from samcli.lib.init.template_modifiers.cli_template_modifier import TemplateModifier
from samcli.lib.init.template_modifiers.xray_tracing_template_modifier import XRayTracingTemplateModifier


class TestTemplateModifier(TestCase):
    def setUp(self):
        self.location = MagicMock()
        self.template_data = [
            "Resources:\n",
            "  HelloWorldFunction:\n",
            "    Type: AWS::Serverless::Function\n",
            "    Properties:\n",
            "      CodeUri: hello_world/\n",
            "      Handler: app.lambda_handler\n",
        ]

    @patch("samcli.lib.init.template_modifiers.cli_template_modifier.TemplateModifier._get_template")
    def test_must_add_new_field_to_template(self, get_template_patch):
        get_template_patch.return_value = [
            "Resources:\n",
            "  HelloWorldFunction:\n",
            "    Type: AWS::Serverless::Function\n",
            "    Properties:\n",
            "      CodeUri: hello_world/\n",
            "      Handler: app.lambda_handler\n",
        ]

        expected_template_data = [
            "# More info about Globals: https://github.com/awslabs/serverless-application-model/blob/master/docs/globals.rst\n",
            "Globals:\n",
            "  Function:\n",
            "    Tracing: Active\n",
            "\n",
            "Resources:\n",
            "  HelloWorldFunction:\n",
            "    Type: AWS::Serverless::Function\n",
            "    Properties:\n",
            "      CodeUri: hello_world/\n",
            "      Handler: app.lambda_handler\n",
        ]

        template_modifier = XRayTracingTemplateModifier(self.location)
        template_modifier._add_new_field_to_template()

        self.assertEqual(template_modifier.template, expected_template_data)

    @patch("samcli.lib.init.template_modifiers.cli_template_modifier.TemplateModifier._get_template")
    def test_must_add_new_function_field_to_template(self, get_template_patch):
        get_template_patch.return_value = [
            "# More info about Globals: https://github.com/awslabs/serverless-application-model/blob/master/docs/globals.rst\n",
            "Globals:\n",
            "  Api:\n",
            "    api_field: field_value\n",
            "\n",
            "Resources:\n",
            "  HelloWorldFunction:\n",
            "    Type: AWS::Serverless::Function\n",
            "    Properties:\n",
            "      CodeUri: hello_world/\n",
            "      Handler: app.lambda_handler\n",
        ]

        expected_template_data = [
            "# More info about Globals: https://github.com/awslabs/serverless-application-model/blob/master/docs/globals.rst\n",
            "Globals:\n",
            "  Api:\n",
            "    api_field: field_value\n",
            "  Function:\n",
            "    Tracing: Active\n",
            "\n",
            "Resources:\n",
            "  HelloWorldFunction:\n",
            "    Type: AWS::Serverless::Function\n",
            "    Properties:\n",
            "      CodeUri: hello_world/\n",
            "      Handler: app.lambda_handler\n",
        ]

        template_modifier = XRayTracingTemplateModifier(self.location)
        template_modifier._add_new_field_to_template()

        self.assertEqual(template_modifier.template, expected_template_data)

    @patch("samcli.lib.init.template_modifiers.cli_template_modifier.TemplateModifier._get_template")
    def test_must_add_new_tracing_field_to_template(self, get_template_patch):
        get_template_patch.return_value = [
            "# More info about Globals: https://github.com/awslabs/serverless-application-model/blob/master/docs/globals.rst\n",
            "Globals:\n",
            "  Function:\n",
            "    Timeout: 3\n",
            "\n",
            "Resources:\n",
            "  HelloWorldFunction:\n",
            "    Type: AWS::Serverless::Function\n",
            "    Properties:\n",
            "      CodeUri: hello_world/\n",
            "      Handler: app.lambda_handler\n",
        ]

        expected_template_data = [
            "# More info about Globals: https://github.com/awslabs/serverless-application-model/blob/master/docs/globals.rst\n",
            "Globals:\n",
            "  Function:\n",
            "    Timeout: 3\n",
            "    Tracing: Active\n",
            "\n",
            "Resources:\n",
            "  HelloWorldFunction:\n",
            "    Type: AWS::Serverless::Function\n",
            "    Properties:\n",
            "      CodeUri: hello_world/\n",
            "      Handler: app.lambda_handler\n",
        ]

        template_modifier = XRayTracingTemplateModifier(self.location)
        template_modifier._add_new_field_to_template()
        self.assertEqual(template_modifier.template, expected_template_data)

    @patch("samcli.lib.init.template_modifiers.cli_template_modifier.TemplateModifier._get_template")
    def test_must_get_section_position(self, get_template_patch):
        get_template_patch.return_value = [
            "# More info about Globals: https://github.com/awslabs/serverless-application-model/blob/master/docs/globals.rst\n",
            "Globals:\n",
            "  Function:\n",
            "    Tracing: Active\n",
            "\n",
            "Resources:\n",
            "  HelloWorldFunction:\n",
            "    Type: AWS::Serverless::Function\n",
            "    Properties:\n",
            "      CodeUri: hello_world/\n",
            "      Handler: app.lambda_handler\n",
        ]

        template_modifier = XRayTracingTemplateModifier(self.location)
        global_location = template_modifier._section_position("Globals:\n")
        function_location = template_modifier._section_position("  Function:\n")
        resource_location = template_modifier._section_position("Resources:\n")

        self.assertEqual(global_location, 1)
        self.assertEqual(function_location, 2)
        self.assertEqual(resource_location, 5)

    @patch("samcli.lib.init.template_modifiers.cli_template_modifier.TemplateModifier._get_template")
    def test_must_get_field_position(self, get_template_patch):
        get_template_patch.return_value = [
            "Resources:\n",
            "  HelloWorldFunction:\n",
            "    Type: AWS::Serverless::Function\n",
            "    Properties:\n",
            "      CodeUri: hello_world/\n",
            "      Handler: app.lambda_handler\n",
        ]

        template_modifier = XRayTracingTemplateModifier(self.location)
        tracing_location = template_modifier._field_position(0, "Tracing")

        self.assertEqual(tracing_location, -1)

    @patch("samcli.lib.init.template_modifiers.xray_tracing_template_modifier.LOG")
    @patch("samcli.lib.init.template_modifiers.cli_template_modifier.parse_yaml_file")
    def test_must_fail_sanity_check(self, parse_yaml_file_mock, log_mock):
        expected_warning_msg = (
            "Warning: Unable to add Tracing to the project. To learn more about Tracing visit "
            "https://docs.aws.amazon.com/serverless-application-model/latest"
            "/developerguide/sam-resource-function.html#sam-function-tracing"
        )
        template_modifier = XRayTracingTemplateModifier(self.location)
        parse_yaml_file_mock.side_effect = ParserError
        result = template_modifier._sanity_check()
        self.assertFalse(result)
        log_mock.warning.assert_called_once_with(expected_warning_msg)

    @patch("samcli.lib.init.template_modifiers.xray_tracing_template_modifier.LOG")
    def test_must_log_warning_message(self, log_mock):
        expected_warning_msg = (
            "Warning: Unable to add Tracing to the project. To learn more about Tracing visit "
            "https://docs.aws.amazon.com/serverless-application-model/latest"
            "/developerguide/sam-resource-function.html#sam-function-tracing"
        )
        template_modifier = XRayTracingTemplateModifier(self.location)
        template_modifier._print_sanity_check_error()
        log_mock.warning.assert_called_once_with(expected_warning_msg)

    @patch("samcli.lib.init.template_modifiers.cli_template_modifier.parse_yaml_file")
    def test_must_pass_sanity_check(self, parse_yaml_file_mock):
        template_modifier = XRayTracingTemplateModifier(self.location)
        parse_yaml_file_mock.return_value = {"add: add_value"}
        result = template_modifier._sanity_check()
        self.assertTrue(result)
