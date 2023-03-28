from unittest import TestCase
from unittest.mock import patch, MagicMock
from yaml.parser import ParserError
from ruamel.yaml import YAML
from io import StringIO

from samcli.lib.init.template_modifiers.xray_tracing_template_modifier import XRayTracingTemplateModifier


class TestTemplateModifier(TestCase):
    def setUp(self):
        self.location = MagicMock()
        self.name = "testApp"
        self.template_location = "/test.yaml"

    @patch(
        "samcli.lib.init.template_modifiers.xray_tracing_template_modifier.XRayTracingTemplateModifier._get_template"
    )
    def test_must_update_template_fields(self, get_template_patch):
        get_template_patch.return_value = {
            "Resources": {
                "HelloWorldFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {"CodeUri": "hello_world", "Handler": "app.lambda_handler"},
                }
            }
        }

        expected_template_data = {
            "Globals": {
                "Function": {
                    "Tracing": "Active",
                },
                "Api": {
                    "TracingEnabled": True,
                },
            },
            "Resources": {
                "HelloWorldFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "CodeUri": "hello_world",
                        "Handler": "app.lambda_handler",
                    },
                }
            },
        }

        template_modifier = XRayTracingTemplateModifier(self.location)
        template_modifier._update_template_fields()

        self.assertEqual(template_modifier.template, expected_template_data)

    @patch(
        "samcli.lib.init.template_modifiers.xray_tracing_template_modifier.XRayTracingTemplateModifier._get_template"
    )
    def test_must_add_new_function_field_to_template(self, get_template_patch):
        get_template_patch.return_value = YAML().load(
            """
# More info about Globals: https://github.com/awslabs/serverless-application-model/blob/master/docs/globals.rst
Globals:
  Api:
    api_field: field_value
Resources:
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: hello_world
      Handler: app.lambda_handler
        """
        )

        expected_template_data = YAML().load(
            """
# More info about Globals: https://github.com/awslabs/serverless-application-model/blob/master/docs/globals.rst
Globals:
  Api:
    api_field: field_value
    TracingEnabled: True
  Function:
    Tracing: Active
Resources:
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: hello_world
      Handler: app.lambda_handler
        """
        )

        template_modifier = XRayTracingTemplateModifier(self.location)
        template_modifier._update_template_fields()
        self.assertEqual(template_modifier.template, expected_template_data)

    @patch(
        "samcli.lib.init.template_modifiers.xray_tracing_template_modifier.XRayTracingTemplateModifier._get_template"
    )
    def test_must_add_new_api_function_field_to_template(self, get_template_patch):
        get_template_patch.return_value = YAML().load(
            """
# More info about Globals: https://github.com/awslabs/serverless-application-model/blob/master/docs/globals.rst
Globals:
  HttpApi:
    http_api_field: field_value
Resources:
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: hello_world
      Handler: app.lambda_handler
        """
        )

        expected_template_data = YAML().load(
            """
# More info about Globals: https://github.com/awslabs/serverless-application-model/blob/master/docs/globals.rst
Globals:
  HttpApi:
    http_api_field: field_value
  Function:
    Tracing: Active
  Api:
    TracingEnabled: True
Resources:
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: hello_world
      Handler: app.lambda_handler
        """
        )

        template_modifier = XRayTracingTemplateModifier(self.location)
        template_modifier._update_template_fields()
        self.assertEqual(template_modifier.template, expected_template_data)

    @patch(
        "samcli.lib.init.template_modifiers.xray_tracing_template_modifier.XRayTracingTemplateModifier._get_template"
    )
    def test_must_replace_new_field_to_template(self, get_template_patch):
        get_template_patch.return_value = YAML().load(
            """
#More info about Globals: https://github.com/awslabs/serverless-application-model/blob/master/docs/globals.rst
Globals:
  Api:
    api_field: field_value
    TracingEnabled: False
  Function:
    function_field: field_value
    Tracing: PassThrough
Resources:
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: hello_world
      Handler: app.lambda_handler
        """
        )

        expected_template_data = YAML().load(
            """
#More info about Globals: https://github.com/awslabs/serverless-application-model/blob/master/docs/globals.rst
Globals:
  Api:
    api_field: field_value
    TracingEnabled: True
  Function:
    function_field: field_value
    Tracing: Active
Resources:
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: hello_world
      Handler: app.lambda_handler
        """
        )

        template_modifier = XRayTracingTemplateModifier(self.location)
        template_modifier._update_template_fields()

        self.assertEqual(template_modifier.template, expected_template_data)

    @patch(
        "samcli.lib.init.template_modifiers.xray_tracing_template_modifier.XRayTracingTemplateModifier._get_template"
    )
    def test_must_add_new_tracing_field_to_template(self, get_template_patch):

        get_template_patch.return_value = YAML().load(
            """
        Globals:
          Function:
            Timeout: 3
        Resources:
          HelloWorldFunction:
            Type: AWS::Serverless::Function
            Properties:
              CodeUri: hello_world
              Handler: app.lambda_handler
        """
        )

        expected_template_data = YAML().load(
            """
        #More info about Globals: https://github.com/awslabs/serverless-application-model/blob/master/docs/globals.rst
        Globals:
          Function:
            Timeout: 3
            Tracing: Active
          Api:
            TracingEnabled: True
        Resources:
          HelloWorldFunction:
            Type: AWS::Serverless::Function
            Properties:
              CodeUri: hello_world
              Handler: app.lambda_handler
        """
        )

        template_modifier = XRayTracingTemplateModifier(self.location)
        template_modifier._update_template_fields()
        self.assertEqual(template_modifier.template, expected_template_data)

    @patch(
        "samcli.lib.init.template_modifiers.xray_tracing_template_modifier.XRayTracingTemplateModifier._get_template"
    )
    def test_comments_are_added(self, get_template_patch):
        get_template_patch.return_value = YAML().load(
            """
        Resources:
          HelloWorldFunction:
            Type: AWS::Serverless::Function
            Properties:
              CodeUri: hello_world
              Handler: app.lambda_handler
        """
        )

        template_modifier = XRayTracingTemplateModifier(self.location)
        template_modifier._update_template_fields()
        buf = StringIO()
        YAML().dump(template_modifier.template, buf)
        self.assertIn("globals.rst", buf.getvalue())

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
