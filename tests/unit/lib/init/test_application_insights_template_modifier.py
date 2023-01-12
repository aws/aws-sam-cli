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
