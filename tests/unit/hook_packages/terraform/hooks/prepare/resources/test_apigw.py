from unittest import TestCase
from unittest.mock import Mock, patch, call

from parameterized import parameterized

from samcli.hook_packages.terraform.hooks.prepare.exceptions import OpenAPIBodyNotSupportedException
from samcli.hook_packages.terraform.hooks.prepare.resources.apigw import (
    _unsupported_reference_field,
    RESTAPITranslationValidator,
    _create_gateway_method_integration,
    _get_reference_from_string_or_intrinsic,
    _gateway_method_integration_identifier,
    _find_gateway_integration,
    add_integrations_to_methods,
    add_integration_responses_to_methods,
    _create_gateway_method_integration_response,
)
from samcli.hook_packages.terraform.hooks.prepare.types import References, TFResource, ConstantValue


class TestRESTAPITranslationValidator(TestCase):
    @patch("samcli.hook_packages.terraform.hooks.prepare.resources.apigw._unsupported_reference_field")
    def test_validate_valid(self, mock_unsupported_reference_field):
        mock_unsupported_reference_field.return_value = False
        validator = RESTAPITranslationValidator({}, TFResource("address", "", Mock(), {}))
        validator.validate()

    @patch("samcli.hook_packages.terraform.hooks.prepare.resources.apigw._unsupported_reference_field")
    def test_validate_invalid(self, mock_unsupported_reference_field):
        mock_unsupported_reference_field.return_value = True
        validator = RESTAPITranslationValidator({}, TFResource("address", "", Mock(), {}))
        with self.assertRaises(OpenAPIBodyNotSupportedException) as ex:
            validator.validate()
        self.assertIn(
            "AWS SAM CLI is unable to process a Terraform project that "
            "uses an OpenAPI specification to define the API Gateway resource.",
            ex.exception.message,
        )

    @parameterized.expand(
        [
            ({"field": "a"}, TFResource("address", "", Mock(), {}), False),
            ({}, TFResource("address", "", Mock(), {"field": ConstantValue("a")}), False),
            ({}, TFResource("address", "", Mock(), {"field": References(["a"])}), True),
        ]
    )
    def test_unsupported_reference_field(self, resource, config_resource, expected):
        result = _unsupported_reference_field("field", resource, config_resource)
        self.assertEqual(result, expected)


class TestMethodToIntegrationLinking(TestCase):
    @patch("samcli.hook_packages.terraform.hooks.prepare.resources.apigw._gateway_method_integration_identifier")
    @patch("samcli.hook_packages.terraform.hooks.prepare.resources.apigw._find_gateway_integration")
    @patch("samcli.hook_packages.terraform.hooks.prepare.resources.apigw._create_gateway_method_integration")
    def test_add_integrations_to_methods(
        self,
        mock_create_gateway_method_integration,
        mock_find_gateway_integration,
        mock_gateway_method_integration_identifier,
    ):
        integration_a = {
            "Type": "Internal::ApiGateway::Method::Integration",
            "Properties": {
                "Uri": "my_cool_invoke_arn",
                "Type": "AWS_PROXY",
                "ResourceId": "MyOtherResource",
                "HttpMethod": "POST",
                "RestApiId": "MyRestApi",
            },
        }
        integration_b = {
            "Type": "Internal::ApiGateway::Method::Integration",
            "Properties": {
                "Uri": "my_cool_invoke_arn",
                "Type": "AWS_PROXY",
                "ResourceId": "MyResource",
                "HttpMethod": "GET",
                "RestApiId": "MyRestApi",
            },
        }
        gateway_integrations = {"MyResourceA": [integration_a], "MyResourceB": [integration_b], "MyResourceC": [Mock()]}
        method_a = {"Type": "AWS::ApiGateway::Method", "Properties": {"HttpMethod": "POST"}}
        method_b = {"Type": "AWS::ApiGateway::Method", "Properties": {"HttpMethod": "GET"}}
        gateway_methods = {
            "MethodA": [method_a],
            "MethodB": [method_b],
        }
        mock_find_gateway_integration.side_effect = [integration_a["Properties"], integration_b["Properties"], None]
        add_integrations_to_methods(gateway_methods, gateway_integrations)
        mock_create_gateway_method_integration.assert_has_calls(
            [
                call(
                    {"Type": "AWS::ApiGateway::Method", "Properties": {"HttpMethod": "POST"}},
                    {
                        "Uri": "my_cool_invoke_arn",
                        "Type": "AWS_PROXY",
                        "ResourceId": "MyOtherResource",
                        "HttpMethod": "POST",
                        "RestApiId": "MyRestApi",
                    },
                ),
                call(
                    {"Type": "AWS::ApiGateway::Method", "Properties": {"HttpMethod": "GET"}},
                    {
                        "Uri": "my_cool_invoke_arn",
                        "Type": "AWS_PROXY",
                        "ResourceId": "MyResource",
                        "HttpMethod": "GET",
                        "RestApiId": "MyRestApi",
                    },
                ),
            ]
        )

    @parameterized.expand(
        [
            (
                {"POST", "MyRestApi", "MyResource"},
                {
                    "MyResourceA": [
                        {
                            "Type": "Internal::ApiGateway::Method::Integration",
                            "Properties": {
                                "Uri": "my_cool_invoke_arn",
                                "Type": "AWS_PROXY",
                                "ResourceId": "MyResource",
                                "HttpMethod": "POST",
                                "RestApiId": "MyRestApi",
                            },
                        }
                    ]
                },
                {
                    "Uri": "my_cool_invoke_arn",
                    "Type": "AWS_PROXY",
                    "ResourceId": "MyResource",
                    "HttpMethod": "POST",
                    "RestApiId": "MyRestApi",
                },
            ),
            (
                {"POST", "MyRestApiOther", "MyResource"},
                {
                    "MyResourceA": [
                        {
                            "Type": "Internal::ApiGateway::Method::Integration",
                            "Properties": {
                                "Uri": "my_cool_invoke_arn",
                                "Type": "AWS_PROXY",
                                "ResourceId": "MyResource",
                                "HttpMethod": "POST",
                                "RestApiId": "MyRestApi",
                            },
                        }
                    ]
                },
                None,
            ),
            (
                {"GET", "MyRestApi", "MyResource"},
                {
                    "MyResourceA": [
                        {
                            "Type": "Internal::ApiGateway::Method::Integration",
                            "Properties": {
                                "Uri": "my_cool_invoke_arn",
                                "Type": "AWS_PROXY",
                                "ResourceId": "MyOtherResource",
                                "HttpMethod": "POST",
                                "RestApiId": "MyRestApi",
                            },
                        }
                    ],
                    "MyResourceB": [
                        {
                            "Type": "Internal::ApiGateway::Method::Integration",
                            "Properties": {
                                "Uri": "my_cool_invoke_arn",
                                "Type": "AWS_PROXY",
                                "ResourceId": "MyResource",
                                "HttpMethod": "GET",
                                "RestApiId": "MyRestApi",
                            },
                        }
                    ],
                },
                {
                    "Uri": "my_cool_invoke_arn",
                    "Type": "AWS_PROXY",
                    "ResourceId": "MyResource",
                    "HttpMethod": "GET",
                    "RestApiId": "MyRestApi",
                },
            ),
        ]
    )
    def test_find_gateway_integration(self, search_key, gateway_integrations_cfn, expected_response):
        response = _find_gateway_integration(search_key, gateway_integrations_cfn)
        self.assertEqual(response, expected_response)

    @parameterized.expand(
        [
            (
                {"HttpMethod": "POST", "RestApiId": "MyRestApi", "ResourceId": "MyResourceId"},
                {"MyRestApi", "MyResourceId", "POST"},
            ),
            (
                {"RestApiId": "MyRestApi", "ResourceId": "MyResourceId"},
                {"MyRestApi", "MyResourceId", ""},
            ),
            (
                {"HttpMethod": "POST", "RestApiId": {"Ref": "MyRestApi"}, "ResourceId": "MyResourceId"},
                {"MyRestApi", "MyResourceId", "POST"},
            ),
            (
                {"HttpMethod": "POST", "RestApiId": {"Ref": "MyRestApi"}, "ResourceId": {"Ref": "MyResourceId"}},
                {"MyRestApi", "MyResourceId", "POST"},
            ),
            (
                {"HttpMethod": "POST", "RestApiId": {"GetAtt": "MyRestApi"}, "ResourceId": {"Ref": "MyResourceId"}},
                {"", "MyResourceId", "POST"},
            ),
        ]
    )
    def test_gateway_method_integration_identifier(self, resource_properties, expected_key):
        key = _gateway_method_integration_identifier(resource_properties)
        self.assertEqual(key, expected_key)

    @parameterized.expand(
        [
            ({"RestApiId": {"Ref": "MyCoolApi"}}, "RestApiId", "MyCoolApi"),
            ({"RestApiId": {"Ref": "MyCoolApi"}}, "RestApiIds", ""),
            ({"RestApiId": "MyCoolApiStringArn"}, "RestApiId", "MyCoolApiStringArn"),
        ]
    )
    def test_get_reference_from_string_or_intrinsic(self, resource_properties, property_key, expected_response):
        response = _get_reference_from_string_or_intrinsic(resource_properties, property_key)
        self.assertEqual(response, expected_response)

    @parameterized.expand(
        [
            (
                {"Type": "AWS::ApiGateway::Method", "Properties": {"HttpMethod": "POST"}},
                {
                    "Random": "property",
                    "Uri": "my_cool_invoke_arn",
                    "Type": "AWS_PROXY",
                    "ContentHandling": "CONVERT_TO_TEXT",
                    "ConnectionType": "INTERNET",
                },
                {
                    "Type": "AWS::ApiGateway::Method",
                    "Properties": {
                        "HttpMethod": "POST",
                        "Integration": {
                            "Uri": "my_cool_invoke_arn",
                            "Type": "AWS_PROXY",
                            "ContentHandling": "CONVERT_TO_TEXT",
                            "ConnectionType": "INTERNET",
                        },
                    },
                },
            ),
            (
                {"Type": "AWS::ApiGateway::Method", "Properties": {}},
                {
                    "Uri": "my_cool_invoke_arn",
                    "Type": "AWS_PROXY",
                },
                {
                    "Type": "AWS::ApiGateway::Method",
                    "Properties": {
                        "Integration": {
                            "Uri": "my_cool_invoke_arn",
                            "Type": "AWS_PROXY",
                        },
                    },
                },
            ),
        ]
    )
    def test_create_gateway_method_integration(
        self, api_gateway_method, integration_resource_properties, expected_method_response
    ):
        _create_gateway_method_integration(api_gateway_method, integration_resource_properties)
        self.assertEqual(api_gateway_method, expected_method_response)


class TestMethodToIntegrationResponseLinking(TestCase):
    @patch("samcli.hook_packages.terraform.hooks.prepare.resources.apigw._gateway_method_integration_identifier")
    @patch("samcli.hook_packages.terraform.hooks.prepare.resources.apigw._find_gateway_integration")
    @patch("samcli.hook_packages.terraform.hooks.prepare.resources.apigw._create_gateway_method_integration_response")
    def test_add_integration_responses_to_methods(
        self,
        mock_create_gateway_method_integration_response,
        mock_find_gateway_integration,
        mock_gateway_method_integration_identifier,
    ):
        integration_response_a = {
            "Type": "Internal::ApiGateway::Method::Integration::Response",
            "Properties": {
                "ResponseParameters": {
                    "parameter_key1": "parameter_value1",
                    "parameter_key2": "parameter_value2",
                }
            },
        }
        integration_response_b = {
            "Type": "Internal::ApiGateway::Method::Integration::Response",
            "Properties": {
                "ResponseParameters": {
                    "parameter_key3": "parameter_value3",
                    "parameter_key4": "parameter_value4",
                }
            },
        }
        gateway_integration_response = {
            "MyResourceA": [integration_response_a],
            "MyResourceB": [integration_response_b],
            "MyResourceC": [Mock()],
        }
        method_a = {
            "Type": "AWS::ApiGateway::Method",
            "Properties": {
                "HttpMethod": "POST",
                "Integration": {"Type": "AWS_PROXY"},
            },
        }
        method_b = {
            "Type": "AWS::ApiGateway::Method",
            "Properties": {
                "HttpMethod": "GET",
                "Integration": {"Type": "AWS_PROXY"},
            },
        }
        gateway_methods = {
            "MethodA": [method_a],
            "MethodB": [method_b],
        }
        mock_find_gateway_integration.side_effect = [
            integration_response_a["Properties"],
            integration_response_b["Properties"],
            None,
        ]
        add_integration_responses_to_methods(gateway_methods, gateway_integration_response)
        mock_create_gateway_method_integration_response.assert_has_calls(
            [
                call(
                    method_a,
                    integration_response_a["Properties"],
                ),
                call(
                    method_b,
                    integration_response_b["Properties"],
                ),
            ]
        )

    @parameterized.expand(
        [
            (
                {"Type": "AWS::ApiGateway::Method", "Properties": {"HttpMethod": "POST"}},
                {
                    "ResponseParameters": {
                        "parameter_key1": "parameter_value1",
                        "parameter_key2": "parameter_value2",
                    }
                },
                {
                    "Type": "AWS::ApiGateway::Method",
                    "Properties": {
                        "HttpMethod": "POST",
                        "Integration": {
                            "IntegrationResponses": [
                                {
                                    "ResponseParameters": {
                                        "parameter_key1": "parameter_value1",
                                        "parameter_key2": "parameter_value2",
                                    }
                                }
                            ]
                        },
                    },
                },
            ),
            (
                {
                    "Type": "AWS::ApiGateway::Method",
                    "Properties": {
                        "HttpMethod": "POST",
                        "Integration": {
                            "Uri": "my_cool_invoke_arn",
                            "Type": "AWS_PROXY",
                        },
                    },
                },
                {
                    "ResponseParameters": {
                        "parameter_key1": "parameter_value1",
                        "parameter_key2": "parameter_value2",
                    }
                },
                {
                    "Type": "AWS::ApiGateway::Method",
                    "Properties": {
                        "HttpMethod": "POST",
                        "Integration": {
                            "Uri": "my_cool_invoke_arn",
                            "Type": "AWS_PROXY",
                            "IntegrationResponses": [
                                {
                                    "ResponseParameters": {
                                        "parameter_key1": "parameter_value1",
                                        "parameter_key2": "parameter_value2",
                                    }
                                }
                            ],
                        },
                    },
                },
            ),
            (
                {
                    "Type": "AWS::ApiGateway::Method",
                    "Properties": {
                        "HttpMethod": "POST",
                        "Integration": {
                            "Uri": "my_cool_invoke_arn",
                            "Type": "AWS_PROXY",
                            "IntegrationResponses": [
                                {
                                    "ResponseParameters": {
                                        "parameter_key3": "parameter_value3",
                                        "parameter_key4": "parameter_value4",
                                    }
                                }
                            ],
                        },
                    },
                },
                {
                    "ResponseParameters": {
                        "parameter_key1": "parameter_value1",
                        "parameter_key2": "parameter_value2",
                    }
                },
                {
                    "Type": "AWS::ApiGateway::Method",
                    "Properties": {
                        "HttpMethod": "POST",
                        "Integration": {
                            "Uri": "my_cool_invoke_arn",
                            "Type": "AWS_PROXY",
                            "IntegrationResponses": [
                                {
                                    "ResponseParameters": {
                                        "parameter_key3": "parameter_value3",
                                        "parameter_key4": "parameter_value4",
                                    }
                                },
                                {
                                    "ResponseParameters": {
                                        "parameter_key1": "parameter_value1",
                                        "parameter_key2": "parameter_value2",
                                    }
                                },
                            ],
                        },
                    },
                },
            ),
        ]
    )
    def test_create_gateway_method_integration_response(
        self, api_gateway_method, integration_response_resource_properties, expected_method_response
    ):
        _create_gateway_method_integration_response(api_gateway_method, integration_response_resource_properties)
        self.assertEqual(api_gateway_method, expected_method_response)
