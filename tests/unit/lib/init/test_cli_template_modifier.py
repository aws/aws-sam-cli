from unittest import TestCase
from unittest.mock import patch, MagicMock
from yaml.parser import ParserError
from collections import OrderedDict

from samcli.lib.init.template_modifiers.cli_template_modifier import TemplateModifier
from samcli.lib.init.template_modifiers.xray_tracing_template_modifier import XRayTracingTemplateModifier
from samcli.lib.init.template_modifiers.application_insights_template_modifier import (
    ApplicationInsightsTemplateModifier,
)


class TestTemplateModifier(TestCase):
    def setUp(self):
        self.location = MagicMock()
        self.name = "testApp"
        self.template_data = [
            "Resources:\n",
            "  HelloWorldFunction:\n",
            "    Type: AWS::Serverless::Function\n",
            "    Properties:\n",
            "      CodeUri: hello_world/\n",
            "      Handler: app.lambda_handler\n",
        ]
        self.template_location = "/test.yaml"

    @patch(
        "samcli.lib.init.template_modifiers.xray_tracing_template_modifier.XRayTracingTemplateModifier._get_template"
    )
    def test_must_update_template_fields(self, get_template_patch):
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
            "  Api:\n",
            "    TracingEnabled: True\n",
            "\n",
            "Resources:\n",
            "  HelloWorldFunction:\n",
            "    Type: AWS::Serverless::Function\n",
            "    Properties:\n",
            "      CodeUri: hello_world/\n",
            "      Handler: app.lambda_handler\n",
        ]

        template_modifier = XRayTracingTemplateModifier(self.location)
        template_modifier._update_template_fields()

        self.assertEqual(template_modifier.template, expected_template_data)

    @patch(
        "samcli.lib.init.template_modifiers.xray_tracing_template_modifier.XRayTracingTemplateModifier._get_template"
    )
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
            "    TracingEnabled: True\n",
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
        template_modifier._update_template_fields()

        self.assertEqual(template_modifier.template, expected_template_data)

    @patch(
        "samcli.lib.init.template_modifiers.xray_tracing_template_modifier.XRayTracingTemplateModifier._get_template"
    )
    def test_must_add_new_api_function_field_to_template(self, get_template_patch):
        get_template_patch.return_value = [
            "# More info about Globals: https://github.com/awslabs/serverless-application-model/blob/master/docs/globals.rst\n",
            "Globals:\n",
            "  HttpApi:\n",
            "    http_api_field: field_value\n",
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
            "  HttpApi:\n",
            "    http_api_field: field_value\n",
            "  Function:\n",
            "    Tracing: Active\n",
            "  Api:\n",
            "    TracingEnabled: True\n",
            "\n",
            "Resources:\n",
            "  HelloWorldFunction:\n",
            "    Type: AWS::Serverless::Function\n",
            "    Properties:\n",
            "      CodeUri: hello_world/\n",
            "      Handler: app.lambda_handler\n",
        ]

        template_modifier = XRayTracingTemplateModifier(self.location)
        template_modifier._update_template_fields()
        self.assertEqual(template_modifier.template, expected_template_data)

    @patch(
        "samcli.lib.init.template_modifiers.xray_tracing_template_modifier.XRayTracingTemplateModifier._get_template"
    )
    def test_must_replace_new_field_to_template(self, get_template_patch):
        get_template_patch.return_value = [
            "# More info about Globals: https://github.com/awslabs/serverless-application-model/blob/master/docs/globals.rst\n",
            "Globals:\n",
            "  Api:\n",
            "    api_field: field_value\n",
            "    TracingEnabled: False\n",
            "  Function:\n",
            "    function_field: field_value\n",
            "    Tracing: PassThrough\n",
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
            "    TracingEnabled: True\n",
            "  Function:\n",
            "    function_field: field_value\n",
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
        template_modifier._update_template_fields()

        self.assertEqual(template_modifier.template, expected_template_data)

    @patch(
        "samcli.lib.init.template_modifiers.xray_tracing_template_modifier.XRayTracingTemplateModifier._get_template"
    )
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
            "  Api:\n",
            "    TracingEnabled: True\n",
            "\n",
            "Resources:\n",
            "  HelloWorldFunction:\n",
            "    Type: AWS::Serverless::Function\n",
            "    Properties:\n",
            "      CodeUri: hello_world/\n",
            "      Handler: app.lambda_handler\n",
        ]

        template_modifier = XRayTracingTemplateModifier(self.location)
        template_modifier._update_template_fields()
        self.assertEqual(template_modifier.template, expected_template_data)

    @patch(
        "samcli.lib.init.template_modifiers.xray_tracing_template_modifier.XRayTracingTemplateModifier._get_template"
    )
    def test_must_get_section_position(self, get_template_patch):
        get_template_patch.return_value = [
            "# More info about Globals: https://github.com/awslabs/serverless-application-model/blob/master/docs/globals.rst\n",
            "Globals:\n",
            "  Function:\n",
            "    Tracing: Active\n",
            "  Api:\n",
            "    TracingEnabled: True\n",
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
        api_location = template_modifier._section_position("  Api:\n")
        resource_location = template_modifier._section_position("Resources:\n")

        self.assertEqual(global_location, 1)
        self.assertEqual(function_location, 2)
        self.assertEqual(api_location, 4)
        self.assertEqual(resource_location, 7)

    @patch(
        "samcli.lib.init.template_modifiers.xray_tracing_template_modifier.XRayTracingTemplateModifier._get_template"
    )
    def test_must_get_section_position_desc(self, get_template_patch):
        get_template_patch.return_value = [
            "# More info about Globals: https://github.com/awslabs/serverless-application-model/blob/master/docs/globals.rst\n",
            "Globals:\n",
            "  Api:\n",
            "    TracingEnabled: True\n",
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
        api_location = template_modifier._section_position("  Api:\n")
        resource_location = template_modifier._section_position("Resources:\n")

        self.assertEqual(global_location, 1)
        self.assertEqual(api_location, 2)
        self.assertEqual(function_location, 4)
        self.assertEqual(resource_location, 7)

    @patch(
        "samcli.lib.init.template_modifiers.xray_tracing_template_modifier.XRayTracingTemplateModifier._get_template"
    )
    def test_must_get_function_field_position(self, get_template_patch):
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

    @patch(
        "samcli.lib.init.template_modifiers.xray_tracing_template_modifier.XRayTracingTemplateModifier._get_template"
    )
    def test_must_get_api_field_position(self, get_template_patch):
        get_template_patch.return_value = [
            "Resources:\n",
            "  HelloWorldFunction:\n",
            "    Type: AWS::Serverless::Function\n",
            "    Properties:\n",
            "      CodeUri: hello_world/\n",
            "      Handler: app.lambda_handler\n",
        ]

        template_modifier = XRayTracingTemplateModifier(self.location)
        tracing_location = template_modifier._field_position(0, "TracingEnabled")

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

    @patch(
        "samcli.lib.init.template_modifiers.application_insights_template_modifier.ApplicationInsightsTemplateModifier._get_template"
    )
    def test_must_add_application_insights_monitoring(self, get_template_patch):
        get_template_patch.return_value = OrderedDict(
            [
                ("AWSTemplateFormatVersion", "2010-09-09"),
                ("Transform", "AWS::Serverless-2016-10-31"),
                ("Description", "testing2\nSample SAM Template for testing2\n"),
                ("Globals", OrderedDict([("Function", OrderedDict([("Timeout", 3)]))])),
                (
                    "Resources",
                    OrderedDict(
                        [
                            (
                                "HelloWorldFunction",
                                OrderedDict(
                                    [
                                        ("Type", "AWS::Serverless::Function"),
                                        (
                                            "Properties",
                                            OrderedDict(
                                                [
                                                    ("CodeUri", "hello_world/"),
                                                    ("Handler", "app.lambda_handler"),
                                                    ("Runtime", "python3.9"),
                                                    ("Architectures", ["x86_64"]),
                                                    (
                                                        "Events",
                                                        OrderedDict(
                                                            [
                                                                (
                                                                    "HelloWorld",
                                                                    OrderedDict(
                                                                        [
                                                                            ("Type", "Api"),
                                                                            (
                                                                                "Properties",
                                                                                OrderedDict(
                                                                                    [
                                                                                        ("Path", "/hello"),
                                                                                        ("Method", "get"),
                                                                                    ]
                                                                                ),
                                                                            ),
                                                                        ]
                                                                    ),
                                                                )
                                                            ]
                                                        ),
                                                    ),
                                                ]
                                            ),
                                        ),
                                    ]
                                ),
                            )
                        ]
                    ),
                ),
            ]
        )

        expected_template_data = OrderedDict(
            [
                ("AWSTemplateFormatVersion", "2010-09-09"),
                ("Transform", "AWS::Serverless-2016-10-31"),
                ("Description", "testing2\nSample SAM Template for testing2\n"),
                ("Globals", OrderedDict([("Function", OrderedDict([("Timeout", 3)]))])),
                (
                    "Resources",
                    OrderedDict(
                        [
                            (
                                "HelloWorldFunction",
                                OrderedDict(
                                    [
                                        ("Type", "AWS::Serverless::Function"),
                                        (
                                            "Properties",
                                            OrderedDict(
                                                [
                                                    ("CodeUri", "hello_world/"),
                                                    ("Handler", "app.lambda_handler"),
                                                    ("Runtime", "python3.9"),
                                                    ("Architectures", ["x86_64"]),
                                                    (
                                                        "Events",
                                                        OrderedDict(
                                                            [
                                                                (
                                                                    "HelloWorld",
                                                                    OrderedDict(
                                                                        [
                                                                            ("Type", "Api"),
                                                                            (
                                                                                "Properties",
                                                                                OrderedDict(
                                                                                    [
                                                                                        ("Path", "/hello"),
                                                                                        ("Method", "get"),
                                                                                    ]
                                                                                ),
                                                                            ),
                                                                        ]
                                                                    ),
                                                                )
                                                            ]
                                                        ),
                                                    ),
                                                ]
                                            ),
                                        ),
                                    ]
                                ),
                            ),
                            (
                                "ApplicationResourceGroup",
                                OrderedDict(
                                    [
                                        ("Type", "AWS::ResourceGroups::Group"),
                                        (
                                            "Properties",
                                            {
                                                "Name": {
                                                    "Fn::Join": [
                                                        "",
                                                        ["ApplicationInsights-SAM-", {"Ref": "AWS::StackName"}],
                                                    ]
                                                },
                                                "ResourceQuery": {"Type": "CLOUDFORMATION_STACK_1_0"},
                                            },
                                        ),
                                    ]
                                ),
                            ),
                            (
                                "ApplicationInsightsMonitoring",
                                OrderedDict(
                                    [
                                        ("Type", "AWS::ApplicationInsights::Application"),
                                        (
                                            "Properties",
                                            {
                                                "ResourceGroupName": {
                                                    "Fn::Join": [
                                                        "",
                                                        ["ApplicationInsights-SAM-", {"Ref": "AWS::StackName"}],
                                                    ]
                                                },
                                                "AutoConfigurationEnabled": "true",
                                            },
                                        ),
                                        ("DependsOn", "ApplicationResourceGroup"),
                                    ]
                                ),
                            ),
                        ]
                    ),
                ),
            ]
        )

        template_modifier = ApplicationInsightsTemplateModifier(self.location)
        template_modifier._update_template_fields()

        print(expected_template_data)
        self.assertEqual(template_modifier.template, expected_template_data)

    @patch("samcli.lib.init.template_modifiers.application_insights_template_modifier.LOG")
    def test_must_log_warning_message_appinsights(self, log_mock):
        expected_warning_msg = (
            "Warning: Unable to add Application Insights monitoring to the application.\n"
            "To learn more about Application Insights, visit "
            "https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/cloudwatch-application-insights.html"
        )
        template_modifier = ApplicationInsightsTemplateModifier(self.location)
        template_modifier._print_sanity_check_error()
        log_mock.warning.assert_called_once_with(expected_warning_msg)
