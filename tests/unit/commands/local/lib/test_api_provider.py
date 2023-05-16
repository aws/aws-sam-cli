from collections import OrderedDict
from unittest import TestCase

from unittest.mock import patch, Mock

from parameterized import parameterized

from samcli.lib.providers.provider import Api, Stack
from samcli.lib.providers.api_provider import ApiProvider
from samcli.lib.providers.sam_api_provider import SamApiProvider
from samcli.lib.providers.cfn_api_provider import CfnApiProvider


class TestApiProvider_init(TestCase):
    @patch.object(ApiProvider, "_extract_api")
    def test_provider_with_valid_template(self, extract_api_mock):
        extract_api_mock.return_value = Api(routes={"set", "of", "values"})
        template = {"Resources": {"a": "b"}}
        stack_mock = Mock(template_dict=template, resources=template["Resources"])

        provider = ApiProvider([stack_mock])
        self.assertEqual(len(provider.routes), 3)
        self.assertEqual(provider.routes, set(["set", "of", "values"]))


class TestApiProviderSelection(TestCase):
    def make_mock_stacks_with_resources(self, resources):
        stack_mock = Mock(resources=resources)
        return [stack_mock]

    def test_default_provider(self):
        resources = {
            "TestApi": {
                "Type": "AWS::UNKNOWN_TYPE",
                "Properties": {
                    "StageName": "dev",
                    "DefinitionBody": {
                        "paths": {
                            "/path": {
                                "get": {
                                    "x-amazon-apigateway-integration": {
                                        "httpMethod": "POST",
                                        "type": "aws_proxy",
                                        "uri": {
                                            "Fn::Sub": "arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31"
                                            "/functions/${NoApiEventFunction.Arn}/invocations"
                                        },
                                        "responses": {},
                                    }
                                }
                            }
                        }
                    },
                },
            }
        }

        provider = ApiProvider.find_api_provider(self.make_mock_stacks_with_resources(resources))
        self.assertTrue(isinstance(provider, SamApiProvider))

    def test_api_provider_sam_api(self):
        resources = {
            "TestApi": {
                "Type": "AWS::Serverless::Api",
                "Properties": {
                    "StageName": "dev",
                    "DefinitionBody": {
                        "paths": {
                            "/path": {
                                "get": {
                                    "x-amazon-apigateway-integration": {
                                        "httpMethod": "POST",
                                        "type": "aws_proxy",
                                        "uri": {
                                            "Fn::Sub": "arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31"
                                            "/functions/${NoApiEventFunction.Arn}/invocations"
                                        },
                                        "responses": {},
                                    }
                                }
                            }
                        }
                    },
                },
            }
        }

        provider = ApiProvider.find_api_provider(self.make_mock_stacks_with_resources(resources))
        self.assertTrue(isinstance(provider, SamApiProvider))

    def test_api_provider_sam_function(self):
        resources = {
            "TestApi": {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    "StageName": "dev",
                    "DefinitionBody": {
                        "paths": {
                            "/path": {
                                "get": {
                                    "x-amazon-apigateway-integration": {
                                        "httpMethod": "POST",
                                        "type": "aws_proxy",
                                        "uri": {
                                            "Fn::Sub": "arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31"
                                            "/functions/${NoApiEventFunction.Arn}/invocations"
                                        },
                                        "responses": {},
                                    }
                                }
                            }
                        }
                    },
                },
            }
        }

        provider = ApiProvider.find_api_provider(self.make_mock_stacks_with_resources(resources))

        self.assertTrue(isinstance(provider, SamApiProvider))

    def test_api_provider_cloud_formation(self):
        resources = {
            "TestApi": {
                "Type": "AWS::ApiGateway::RestApi",
                "Properties": {
                    "StageName": "dev",
                    "Body": {
                        "paths": {
                            "/path": {
                                "get": {
                                    "x-amazon-apigateway-integration": {
                                        "httpMethod": "POST",
                                        "type": "aws_proxy",
                                        "uri": {
                                            "Fn::Sub": "arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31"
                                            "/functions/${NoApiEventFunction.Arn}/invocations"
                                        },
                                        "responses": {},
                                    }
                                }
                            }
                        }
                    },
                },
            }
        }

        provider = ApiProvider.find_api_provider(self.make_mock_stacks_with_resources(resources))
        self.assertTrue(isinstance(provider, CfnApiProvider))

    def test_multiple_api_provider_cloud_formation(self):
        resources = OrderedDict()
        resources["TestApi"] = {
            "Type": "AWS::ApiGateway::RestApi",
            "Properties": {
                "StageName": "dev",
                "Body": {
                    "paths": {
                        "/path": {
                            "get": {
                                "x-amazon-apigateway-integration": {
                                    "httpMethod": "POST",
                                    "type": "aws_proxy",
                                    "uri": {
                                        "Fn::Sub": "arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31"
                                        "/functions/${NoApiEventFunction.Arn}/invocations"
                                    },
                                    "responses": {},
                                }
                            }
                        }
                    }
                },
            },
        }
        resources["OtherApi"] = {
            "Type": "AWS::Serverless::Api",
            "Properties": {
                "StageName": "dev",
                "DefinitionBody": {
                    "paths": {
                        "/path": {
                            "get": {
                                "x-amazon-apigateway-integration": {
                                    "httpMethod": "POST",
                                    "type": "aws_proxy",
                                    "uri": {
                                        "Fn::Sub": "arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31"
                                        "/functions/${NoApiEventFunction.Arn}/invocations"
                                    },
                                    "responses": {},
                                }
                            }
                        }
                    }
                },
            },
        }

        provider = ApiProvider.find_api_provider(self.make_mock_stacks_with_resources(resources))
        self.assertTrue(isinstance(provider, CfnApiProvider))


class TestApiProvider_merge_routes(TestCase):
    @parameterized.expand([("", 0), ("A", 1), ("A/B/C", 3)])
    def test_get_route_stack_depth(self, stack_path, expected_depth):
        route = Mock(stack_path=stack_path)
        self.assertEqual(SamApiProvider._get_route_stack_depth(route), expected_depth)

    def test_explicit_apis_overridden_by_implicit(self):
        explicit1 = Mock(stack_path="", methods=["GET"], path="/")
        explicit2 = Mock(stack_path="", methods=["GET"], path="/")
        explicits = [explicit1, explicit2]
        implicits = [Mock(stack_path="", methods=["GET"], path="/")]

        collector = [
            ("explicitApiLogicalID", [explicit1]),
            (SamApiProvider.IMPLICIT_API_RESOURCE_ID, implicits),
            ("explicitApiLogicalID2", [explicit2]),
        ]
        self.assertEqual(SamApiProvider.merge_routes(collector), implicits)

    @parameterized.expand(
        [
            (SamApiProvider.IMPLICIT_API_RESOURCE_ID,),
            (SamApiProvider.IMPLICIT_HTTP_API_RESOURCE_ID,),
            ("explicitLogicalId",),
        ]
    )
    def test_apis_in_child_stack_overridden_by_apis_in_parents_within_implicit_or_explicit(self, logicalId):
        route1 = Mock(stack_path="", methods=["GET"], path="/")
        route2 = Mock(stack_path="A", methods=["GET"], path="/")
        route3 = Mock(stack_path="A/B/C", methods=["GET"], path="/")

        collector = [
            (logicalId, [route3]),
            (logicalId, [route1]),
            (logicalId, [route2]),
        ]
        self.assertEqual(SamApiProvider.merge_routes(collector), [route1])


class TestApiProvider_check_implicit_api_resource_ids(TestCase):
    @patch("samcli.lib.providers.sam_base_provider.SamBaseProvider.get_template")
    @patch("samcli.lib.providers.sam_api_provider.LOG.warning")
    def test_check_implicit_api_resource_ids_false(self, warning_mock, get_template_mock):
        SamApiProvider.check_implicit_api_resource_ids(
            [Stack("", "stack", "location", None, {"Resources": {"Api1": {"Properties": Mock()}}})]
        )
        warning_mock.assert_not_called()
        get_template_mock.assert_not_called()

    @patch("samcli.lib.providers.sam_base_provider.SamBaseProvider.get_template")
    @patch("samcli.lib.providers.sam_api_provider.LOG.warning")
    def test_check_implicit_api_resource_ids_rest_api(self, warning_mock, get_template_mock):
        SamApiProvider.check_implicit_api_resource_ids(
            [
                Stack(
                    "",
                    "stack",
                    "location",
                    None,
                    {"Resources": {"Api1": {"Properties": Mock()}, "ServerlessRestApi": {"Properties": Mock()}}},
                )
            ]
        )
        warning_mock.assert_called_once()
        get_template_mock.assert_not_called()

    @patch("samcli.lib.providers.sam_base_provider.SamBaseProvider.get_template")
    @patch("samcli.lib.providers.sam_api_provider.LOG.warning")
    def test_check_implicit_api_resource_ids_http_api(self, warning_mock, get_template_mock):
        SamApiProvider.check_implicit_api_resource_ids(
            [
                Stack(
                    "",
                    "stack",
                    "location",
                    None,
                    {"Resources": {"Api1": {"Properties": Mock()}, "ServerlessHttpApi": {"Properties": Mock()}}},
                )
            ]
        )
        warning_mock.assert_called_once()
        get_template_mock.assert_not_called()
