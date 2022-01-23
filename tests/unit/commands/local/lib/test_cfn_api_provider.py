import json
import tempfile
from collections import OrderedDict
from unittest import TestCase

from unittest.mock import patch, Mock

from samcli.lib.providers.api_provider import ApiProvider
from samcli.lib.providers.cfn_api_provider import CfnApiProvider
from samcli.local.apigw.local_apigw_service import Route
from tests.unit.commands.local.lib.test_sam_api_provider import make_swagger
from samcli.lib.providers.provider import Cors, Stack


def make_mock_stacks_from_template(template):
    stack_mock = Stack("", "", Mock(), parameters=None, template_dict=template)
    return [stack_mock]


class TestApiProviderWithApiGatewayRestRoute(TestCase):
    def setUp(self):
        self.binary_types = ["image/png", "image/jpg"]
        self.input_routes = [
            Route(path="/path1", methods=["GET", "POST"], function_name="SamFunc1"),
            Route(path="/path2", methods=["PUT", "GET"], function_name="SamFunc1"),
            Route(path="/path3", methods=["DELETE"], function_name="SamFunc1"),
        ]

    def test_with_no_apis(self):
        template = {"Resources": {"Api1": {"Type": "AWS::ApiGateway::RestApi", "Properties": {}}}}

        provider = ApiProvider(make_mock_stacks_from_template(template))

        self.assertEqual(provider.routes, [])

    def test_with_inline_swagger_apis(self):
        template = {
            "Resources": {
                "Api1": {"Type": "AWS::ApiGateway::RestApi", "Properties": {"Body": make_swagger(self.input_routes)}}
            }
        }

        provider = ApiProvider(make_mock_stacks_from_template(template))
        self.assertCountEqual(self.input_routes, provider.routes)

    def test_with_swagger_as_local_file(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as fp:
            filename = fp.name

            swagger = make_swagger(self.input_routes)

            json.dump(swagger, fp)
            fp.flush()

            template = {
                "Resources": {"Api1": {"Type": "AWS::ApiGateway::RestApi", "Properties": {"BodyS3Location": filename}}}
            }

            provider = ApiProvider(make_mock_stacks_from_template(template))
            self.assertCountEqual(self.input_routes, provider.routes)

    def test_body_with_swagger_as_local_file_expect_fail(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as fp:
            filename = fp.name

            swagger = make_swagger(self.input_routes)

            json.dump(swagger, fp)
            fp.flush()

            template = {"Resources": {"Api1": {"Type": "AWS::ApiGateway::RestApi", "Properties": {"Body": filename}}}}
            self.assertRaises(Exception, ApiProvider, template)

    @patch("samcli.lib.providers.cfn_base_api_provider.SwaggerReader")
    def test_with_swagger_as_both_body_and_uri_called(self, SwaggerReaderMock):
        body = {"some": "body"}
        filename = "somefile.txt"

        template = {
            "Resources": {
                "Api1": {"Type": "AWS::ApiGateway::RestApi", "Properties": {"BodyS3Location": filename, "Body": body}}
            }
        }

        SwaggerReaderMock.return_value.read.return_value = make_swagger(self.input_routes)

        cwd = "foo"
        provider = ApiProvider(make_mock_stacks_from_template(template), cwd=cwd)
        self.assertCountEqual(self.input_routes, provider.routes)
        SwaggerReaderMock.assert_called_with(definition_body=body, definition_uri=filename, working_dir=cwd)

    def test_swagger_with_any_method(self):
        routes = [Route(path="/path", methods=["any"], function_name="SamFunc1")]

        expected_routes = [
            Route(
                path="/path",
                methods=["GET", "DELETE", "PUT", "POST", "HEAD", "OPTIONS", "PATCH"],
                function_name="SamFunc1",
            )
        ]

        template = {
            "Resources": {"Api1": {"Type": "AWS::ApiGateway::RestApi", "Properties": {"Body": make_swagger(routes)}}}
        }

        provider = ApiProvider(make_mock_stacks_from_template(template))
        self.assertCountEqual(expected_routes, provider.routes)

    def test_with_binary_media_types(self):
        template = {
            "Resources": {
                "Api1": {
                    "Type": "AWS::ApiGateway::RestApi",
                    "Properties": {"Body": make_swagger(self.input_routes, binary_media_types=self.binary_types)},
                }
            }
        }

        expected_binary_types = sorted(self.binary_types)
        expected_apis = [
            Route(path="/path1", methods=["GET", "POST"], function_name="SamFunc1"),
            Route(path="/path2", methods=["PUT", "GET"], function_name="SamFunc1"),
            Route(path="/path3", methods=["DELETE"], function_name="SamFunc1"),
        ]

        provider = ApiProvider(make_mock_stacks_from_template(template))
        self.assertCountEqual(expected_apis, provider.routes)
        self.assertCountEqual(provider.api.binary_media_types, expected_binary_types)

    def test_with_binary_media_types_in_swagger_and_on_resource(self):
        input_routes = [Route(path="/path", methods=["OPTIONS"], function_name="SamFunc1")]
        extra_binary_types = ["text/html"]

        template = {
            "Resources": {
                "Api1": {
                    "Type": "AWS::ApiGateway::RestApi",
                    "Properties": {
                        "BinaryMediaTypes": extra_binary_types,
                        "Body": make_swagger(input_routes, binary_media_types=self.binary_types),
                    },
                }
            }
        }

        expected_binary_types = sorted(self.binary_types + extra_binary_types)
        expected_routes = [Route(path="/path", methods=["OPTIONS"], function_name="SamFunc1")]

        provider = ApiProvider(make_mock_stacks_from_template(template))
        self.assertCountEqual(expected_routes, provider.routes)
        self.assertCountEqual(provider.api.binary_media_types, expected_binary_types)


class TestCloudFormationStageValues(TestCase):
    def setUp(self):
        self.binary_types = ["image/png", "image/jpg"]
        self.input_routes = [
            Route(path="/path1", methods=["GET", "POST"], function_name="SamFunc1"),
            Route(path="/path2", methods=["PUT", "GET"], function_name="SamFunc1"),
            Route(path="/path3", methods=["DELETE"], function_name="SamFunc1"),
        ]

    def test_provider_parse_stage_name(self):
        template = {
            "Resources": {
                "Stage": {"Type": "AWS::ApiGateway::Stage", "Properties": {"StageName": "dev", "RestApiId": "TestApi"}},
                "TestApi": {
                    "Type": "AWS::ApiGateway::RestApi",
                    "Properties": {
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
                        }
                    },
                },
            }
        }
        provider = ApiProvider(make_mock_stacks_from_template(template))
        route1 = Route(path="/path", methods=["GET"], function_name="NoApiEventFunction")

        self.assertIn(route1, provider.routes)
        self.assertEqual(provider.api.stage_name, "dev")
        self.assertEqual(provider.api.stage_variables, None)

    def test_provider_stage_variables(self):
        template = {
            "Resources": {
                "Stage": {
                    "Type": "AWS::ApiGateway::Stage",
                    "Properties": {
                        "StageName": "dev",
                        "Variables": {"vis": "data", "random": "test", "foo": "bar"},
                        "RestApiId": "TestApi",
                    },
                },
                "TestApi": {
                    "Type": "AWS::ApiGateway::RestApi",
                    "Properties": {
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
                        }
                    },
                },
            }
        }
        provider = ApiProvider(make_mock_stacks_from_template(template))
        route1 = Route(path="/path", methods=["GET"], function_name="NoApiEventFunction")
        self.assertIn(route1, provider.routes)
        self.assertEqual(provider.api.stage_name, "dev")
        self.assertEqual(provider.api.stage_variables, {"vis": "data", "random": "test", "foo": "bar"})

    def test_multi_stage_get_all(self):
        resources = OrderedDict(
            {
                "ProductionApi": {
                    "Type": "AWS::ApiGateway::RestApi",
                    "Properties": {
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
                                },
                                "/anotherpath": {
                                    "post": {
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
                                },
                            }
                        }
                    },
                }
            }
        )
        resources["StageDev"] = {
            "Type": "AWS::ApiGateway::Stage",
            "Properties": {
                "StageName": "dev",
                "Variables": {"vis": "data", "random": "test", "foo": "bar"},
                "RestApiId": "ProductionApi",
            },
        }
        resources["StageProd"] = {
            "Type": "AWS::ApiGateway::Stage",
            "Properties": {
                "StageName": "Production",
                "Variables": {"vis": "prod data", "random": "test", "foo": "bar"},
                "RestApiId": "ProductionApi",
            },
        }
        template = {"Resources": resources}
        provider = ApiProvider(make_mock_stacks_from_template(template))

        result = [f for f in provider.get_all()]
        routes = result[0].routes

        route1 = Route(path="/path", methods=["GET"], function_name="NoApiEventFunction")
        route2 = Route(path="/anotherpath", methods=["POST"], function_name="NoApiEventFunction")
        self.assertEqual(len(routes), 2)
        self.assertIn(route1, routes)
        self.assertIn(route2, routes)

        self.assertEqual(provider.api.stage_name, "Production")
        self.assertEqual(provider.api.stage_variables, {"vis": "prod data", "random": "test", "foo": "bar"})


class TestCloudFormationResourceMethod(TestCase):
    def setUp(self):
        self.binary_types = ["image/png", "image/jpg"]
        self.input_routes = [
            Route(path="/path1", methods=["GET", "POST"], function_name="SamFunc1"),
            Route(path="/path2", methods=["PUT", "GET"], function_name="SamFunc1"),
            Route(path="/path3", methods=["DELETE"], function_name="SamFunc1"),
        ]

    def test_basic_rest_api_resource_method(self):
        template = {
            "Resources": {
                "TestApi": {"Type": "AWS::ApiGateway::RestApi", "Properties": {"StageName": "Prod"}},
                "ApiResource": {"Properties": {"PathPart": "{proxy+}", "RestApiId": "TestApi"}},
                "ApiMethod": {
                    "Type": "AWS::ApiGateway::Method",
                    "Properties": {"HttpMethod": "POST", "RestApiId": "TestApi", "ResourceId": "ApiResource"},
                },
            }
        }

        provider = ApiProvider(make_mock_stacks_from_template(template))

        self.assertEqual(provider.routes, [Route(function_name=None, path="/{proxy+}", methods=["POST"])])

    def test_resolve_correct_resource_path(self):
        resources = {
            "RootApiResource": {
                "Tyoe": "AWS::ApiGateway::Resource",
                "Properties": {"PathPart": "root", "ResourceId": "TestApi"},
            }
        }
        beta_resource = {
            "Tyoe": "AWS::ApiGateway::Resource",
            "Properties": {"PathPart": "beta", "ResourceId": "TestApi", "ParentId": "RootApiResource"},
        }
        resources["BetaApiResource"] = beta_resource
        provider = CfnApiProvider()
        full_path = provider.resolve_resource_path(resources, beta_resource, "/test")
        self.assertEqual(full_path, "/root/beta/test")

    def test_resolve_correct_multi_parent_resource_path(self):
        template = {
            "Resources": {
                "TestApi": {"Type": "AWS::ApiGateway::Resource", "Properties": {"StageName": "Prod"}},
                "RootApiResource": {
                    "Type": "AWS::ApiGateway::Resource",
                    "Properties": {"PathPart": "root", "ResourceId": "TestApi"},
                },
                "V1ApiResource": {
                    "Type": "AWS::ApiGateway::Resource",
                    "Properties": {"PathPart": "v1", "ResourceId": "TestApi", "ParentId": "RootApiResource"},
                },
                "AlphaApiResource": {
                    "Type": "AWS::ApiGateway::Resource",
                    "Properties": {"PathPart": "alpha", "ResourceId": "TestApi", "ParentId": "V1ApiResource"},
                },
                "BetaApiResource": {
                    "Type": "AWS::ApiGateway::Resource",
                    "Properties": {"PathPart": "beta", "ResourceId": "TestApi", "ParentId": "V1ApiResource"},
                },
                "AlphaApiMethod": {
                    "Type": "AWS::ApiGateway::Method",
                    "Properties": {"HttpMethod": "GET", "RestApiId": "TestApi", "ResourceId": "AlphaApiResource"},
                },
                "BetaAlphaApiMethod": {
                    "Type": "AWS::ApiGateway::Method",
                    "Properties": {"HttpMethod": "POST", "RestApiId": "TestApi", "ResourceId": "BetaApiResource"},
                },
            }
        }

        provider = ApiProvider(make_mock_stacks_from_template(template))
        self.assertCountEqual(
            provider.routes,
            [
                Route(path="/root/v1/beta", methods=["POST"], function_name=None),
                Route(path="/root/v1/alpha", methods=["GET"], function_name=None),
            ],
        )

    def test_resource_with_method_correct_routes(self):
        template = {
            "Resources": {
                "TestApi": {"Type": "AWS::ApiGateway::Resource", "Properties": {"StageName": "Prod"}},
                "BetaApiResource": {
                    "Type": "AWS::ApiGateway::Resource",
                    "Properties": {"PathPart": "beta", "ResourceId": "TestApi"},
                },
                "BetaAlphaApiMethod": {
                    "Type": "AWS::ApiGateway::Method",
                    "Properties": {"HttpMethod": "ANY", "RestApiId": "TestApi", "ResourceId": "BetaApiResource"},
                },
            }
        }
        provider = ApiProvider(make_mock_stacks_from_template(template))
        self.assertCountEqual(
            provider.routes,
            [
                Route(
                    path="/beta",
                    methods=["POST", "GET", "DELETE", "HEAD", "OPTIONS", "PATCH", "PUT"],
                    function_name=None,
                )
            ],
        )

    def test_method_integration_uri(self):
        template = {
            "Resources": {
                "TestApi": {"Type": "AWS::ApiGateway::Resource", "Properties": {"StageName": "Prod"}},
                "RootApiResource": {
                    "Type": "AWS::ApiGateway::Resource",
                    "Properties": {"PathPart": "root", "ResourceId": "TestApi"},
                },
                "V1ApiResource": {
                    "Type": "AWS::ApiGateway::Resource",
                    "Properties": {"PathPart": "v1", "ResourceId": "TestApi", "ParentId": "RootApiResource"},
                },
                "AlphaApiResource": {
                    "Type": "AWS::ApiGateway::Resource",
                    "Properties": {"PathPart": "alpha", "ResourceId": "TestApi", "ParentId": "V1ApiResource"},
                },
                "BetaApiResource": {
                    "Type": "AWS::ApiGateway::Resource",
                    "Properties": {"PathPart": "beta", "ResourceId": "TestApi", "ParentId": "V1ApiResource"},
                },
                "AlphaApiMethod": {
                    "Type": "AWS::ApiGateway::Method",
                    "Properties": {
                        "HttpMethod": "GET",
                        "RestApiId": "TestApi",
                        "ResourceId": "AlphaApiResource",
                        "Integration": {
                            "Uri": {
                                "Fn::Sub": "arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/"
                                "functions"
                                "/${AWSBetaLambdaFunction.Arn}/invocations} "
                            }
                        },
                    },
                },
                "BetaAlphaApiMethod": {
                    "Type": "AWS::ApiGateway::Method",
                    "Properties": {
                        "HttpMethod": "POST",
                        "RestApiId": "TestApi",
                        "ResourceId": "BetaApiResource",
                        "Integration": {
                            "Uri": {
                                "Fn::Sub": "arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/"
                                "functions"
                                "/${AWSLambdaFunction.Arn}/invocations}"
                            }
                        },
                    },
                },
                "AWSAlphaLambdaFunction": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {"Code": ".", "Handler": "main.run_test", "Runtime": "Python3.6"},
                },
                "AWSBetaLambdaFunction": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {"Code": ".", "Handler": "main.run_test", "Runtime": "Python3.6"},
                },
            }
        }

        provider = ApiProvider(make_mock_stacks_from_template(template))
        self.assertCountEqual(
            provider.routes,
            [
                Route(path="/root/v1/beta", methods=["POST"], function_name="AWSLambdaFunction"),
                Route(path="/root/v1/alpha", methods=["GET"], function_name="AWSBetaLambdaFunction"),
            ],
        )

    def test_binary_media_types_method(self):
        template = {
            "Resources": {
                "TestApi": {"Type": "AWS::ApiGateway::Resource", "Properties": {"StageName": "Prod"}},
                "RootApiResource": {
                    "Type": "AWS::ApiGateway::Resource",
                    "Properties": {"PathPart": "root", "ResourceId": "TestApi"},
                },
                "V1ApiResource": {
                    "Type": "AWS::ApiGateway::Resource",
                    "Properties": {"PathPart": "v1", "ResourceId": "TestApi", "ParentId": "RootApiResource"},
                },
                "AlphaApiResource": {
                    "Type": "AWS::ApiGateway::Resource",
                    "Properties": {"PathPart": "alpha", "ResourceId": "TestApi", "ParentId": "V1ApiResource"},
                },
                "BetaApiResource": {
                    "Type": "AWS::ApiGateway::Resource",
                    "Properties": {"PathPart": "beta", "ResourceId": "TestApi", "ParentId": "V1ApiResource"},
                },
                "AlphaApiMethod": {
                    "Type": "AWS::ApiGateway::Method",
                    "Properties": {
                        "HttpMethod": "GET",
                        "RestApiId": "TestApi",
                        "ResourceId": "AlphaApiResource",
                        "Integration": {
                            "Uri": {
                                "Fn::Sub": "arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/"
                                "functions"
                                "/${AWSBetaLambdaFunction.Arn}/invocations} "
                            },
                            "ContentHandling": "CONVERT_TO_BINARY",
                            "ContentType": "image~1jpg",
                        },
                    },
                },
                "BetaAlphaApiMethod": {
                    "Type": "AWS::ApiGateway::Method",
                    "Properties": {
                        "HttpMethod": "POST",
                        "RestApiId": "TestApi",
                        "ResourceId": "BetaApiResource",
                        "Integration": {
                            "Uri": {
                                "Fn::Sub": "arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/"
                                "functions"
                                "/${AWSLambdaFunction.Arn}/invocations}"
                            },
                            "ContentHandling": "CONVERT_TO_BINARY",
                            "ContentType": "image~1png",
                        },
                    },
                },
                "AWSAlphaLambdaFunction": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {"Code": ".", "Handler": "main.run_test", "Runtime": "Python3.6"},
                },
                "AWSBetaLambdaFunction": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {"Code": ".", "Handler": "main.run_test", "Runtime": "Python3.6"},
                },
            }
        }

        provider = ApiProvider(make_mock_stacks_from_template(template))
        self.assertCountEqual(provider.api.binary_media_types, ["image/png", "image/jpg"])

    def test_cdk(self):
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Resources": {
                "HelloHandler2E4FBA4D": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {"Code": ".", "Handler": "main.handler", "Runtime": "python3.6"},
                    "DependsOn": ["HelloHandlerServiceRole11EF7C63"],
                },
                "EndpointEEF1FD8F": {"Type": "AWS::ApiGateway::RestApi", "Properties": {"Name": "Endpoint"}},
                "EndpointDeploymentStageprodB78BEEA0": {
                    "Type": "AWS::ApiGateway::Stage",
                    "Properties": {
                        "RestApiId": {"Ref": "EndpointEEF1FD8F"},
                        "DeploymentId": {"Ref": "EndpointDeployment318525DA37c0e38727e25b4317827bf43e918fbf"},
                        "StageName": "prod",
                    },
                },
                "Endpointproxy39E2174E": {
                    "Type": "AWS::ApiGateway::Resource",
                    "Properties": {
                        "ParentId": {"Fn::GetAtt": ["EndpointEEF1FD8F", "RootResourceId"]},
                        "PathPart": "{proxy+}",
                        "RestApiId": {"Ref": "EndpointEEF1FD8F"},
                    },
                },
                "EndpointproxyANYC09721C5": {
                    "Type": "AWS::ApiGateway::Method",
                    "Properties": {
                        "HttpMethod": "ANY",
                        "ResourceId": {"Ref": "Endpointproxy39E2174E"},
                        "RestApiId": {"Ref": "EndpointEEF1FD8F"},
                        "AuthorizationType": "NONE",
                        "Integration": {
                            "IntegrationHttpMethod": "POST",
                            "Type": "AWS_PROXY",
                            "Uri": {
                                "Fn::Join": [
                                    "",
                                    [
                                        "arn:",
                                        {"Ref": "AWS::Partition"},
                                        ":apigateway:",
                                        {"Ref": "AWS::Region"},
                                        "lambda:path/2015-03-31/functions/",
                                        {"Fn::GetAtt": ["HelloHandler2E4FBA4D", "Arn"]},
                                        "/invocations",
                                    ],
                                ]
                            },
                        },
                    },
                },
                "EndpointANY485C938B": {
                    "Type": "AWS::ApiGateway::Method",
                    "Properties": {
                        "HttpMethod": "ANY",
                        "ResourceId": {"Fn::GetAtt": ["EndpointEEF1FD8F", "RootResourceId"]},
                        "RestApiId": {"Ref": "EndpointEEF1FD8F"},
                        "AuthorizationType": "NONE",
                        "Integration": {
                            "IntegrationHttpMethod": "POST",
                            "Type": "AWS_PROXY",
                            "Uri": {
                                "Fn::Join": [
                                    "",
                                    [
                                        "arn:",
                                        {"Ref": "AWS::Partition"},
                                        ":apigateway:",
                                        {"Ref": "AWS::Region"},
                                        "lambda:path/2015-03-31/functions/",
                                        {"Fn::GetAtt": ["HelloHandler2E4FBA4D", "Arn"]},
                                        "/invocations",
                                    ],
                                ]
                            },
                        },
                    },
                },
            },
            "Parameters": {
                "HelloHandlerCodeS3Bucket4359A483": {
                    "Type": "String",
                    "Description": 'S3 bucket for asset "CdkWorkshopStack/HelloHandler/Code"',
                },
                "HelloHandlerCodeS3VersionKey07D12610": {
                    "Type": "String",
                    "Description": 'S3 key for asset version "CdkWorkshopStack/HelloHandler/Code"',
                },
            },
            "Outputs": {
                "Endpoint8024A810": {
                    "Value": {
                        "Fn::Join": [
                            "",
                            [
                                "https://",
                                {"Ref": "EndpointEEF1FD8F"},
                                ".execute-api.",
                                {"Ref": "AWS::Region"},
                                ".",
                                {"Ref": "AWS::URLSuffix"},
                                "/",
                                {"Ref": "EndpointDeploymentStageprodB78BEEA0"},
                                "/",
                            ],
                        ]
                    },
                    "Export": {"Name": "CdkWorkshopStack:Endpoint8024A810"},
                }
            },
        }
        provider = ApiProvider(make_mock_stacks_from_template(template))
        proxy_paths = [Route(path="/{proxy+}", methods=Route.ANY_HTTP_METHODS, function_name="HelloHandler2E4FBA4D")]
        root_paths = [Route(path="/", methods=Route.ANY_HTTP_METHODS, function_name="HelloHandler2E4FBA4D")]
        self.assertCountEqual(provider.routes, proxy_paths + root_paths)


class TestCloudFormationProviderWithApiGatewayV2(TestCase):
    def setUp(self):
        self.input_routes = [
            Route(path="/path1", methods=["GET", "POST"], function_name="SamFunc1"),
            Route(path="/path2", methods=["PUT", "GET"], function_name="SamFunc1"),
            Route(path="/path3", methods=["DELETE"], function_name="SamFunc1"),
        ]

    def test_with_no_apis(self):
        template = {"Resources": {"Api1": {"Type": "AWS::ApiGatewayV2::Api", "Properties": {}}}}

        provider = ApiProvider(make_mock_stacks_from_template(template))

        self.assertEqual(provider.routes, [])

    def test_with_inline_swagger_apis(self):
        template = {
            "Resources": {
                "Api1": {"Type": "AWS::ApiGatewayV2::Api", "Properties": {"Body": make_swagger(self.input_routes)}}
            }
        }

        provider = ApiProvider(make_mock_stacks_from_template(template))
        self.assertCountEqual(self.input_routes, provider.routes)

    def test_with_swagger_as_local_file(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as fp:
            filename = fp.name

            swagger = make_swagger(self.input_routes)

            json.dump(swagger, fp)
            fp.flush()

            template = {
                "Resources": {"Api1": {"Type": "AWS::ApiGatewayV2::Api", "Properties": {"BodyS3Location": filename}}}
            }

            provider = ApiProvider(make_mock_stacks_from_template(template))
            self.assertCountEqual(self.input_routes, provider.routes)

    def test_body_with_swagger_as_local_file_expect_fail(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as fp:
            filename = fp.name

            swagger = make_swagger(self.input_routes)

            json.dump(swagger, fp)
            fp.flush()

            template = {"Resources": {"Api1": {"Type": "AWS::ApiGatewayV2::Api", "Properties": {"Body": filename}}}}
            self.assertRaises(Exception, ApiProvider, template)

    @patch("samcli.lib.providers.cfn_base_api_provider.SwaggerReader")
    def test_with_swagger_as_both_body_and_uri_called(self, SwaggerReaderMock):
        body = {"some": "body"}
        filename = "somefile.txt"

        template = {
            "Resources": {
                "Api1": {"Type": "AWS::ApiGatewayV2::Api", "Properties": {"BodyS3Location": filename, "Body": body}}
            }
        }

        SwaggerReaderMock.return_value.read.return_value = make_swagger(self.input_routes)

        cwd = "foo"
        provider = ApiProvider(make_mock_stacks_from_template(template), cwd=cwd)
        self.assertCountEqual(self.input_routes, provider.routes)
        SwaggerReaderMock.assert_called_with(definition_body=body, definition_uri=filename, working_dir=cwd)

    def test_swagger_with_any_method(self):
        routes = [Route(path="$default", methods=["any"], function_name="SamFunc1")]

        expected_routes = [
            Route(
                path="$default",
                methods=["GET", "DELETE", "PUT", "POST", "HEAD", "OPTIONS", "PATCH"],
                function_name="SamFunc1",
            )
        ]

        template = {
            "Resources": {"Api1": {"Type": "AWS::ApiGatewayV2::Api", "Properties": {"Body": make_swagger(routes)}}}
        }

        provider = ApiProvider(make_mock_stacks_from_template(template))
        self.assertEqual(expected_routes, provider.routes)

    def test_with_quick_create_default_route(self):
        expected_routes = [
            Route(
                path="$default",
                methods=["X-AMAZON-APIGATEWAY-ANY-METHOD"],
                function_name="SamFunc1",
            )
        ]

        template = {
            "Resources": {
                "Api1": {
                    "Type": "AWS::ApiGatewayV2::Api",
                    "Properties": {
                        "Target": "arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east-1"
                        ":123456789012:function:SamFunc1/invocations",
                        "ProtocolType": "HTTP",
                    },
                }
            }
        }

        provider = ApiProvider(make_mock_stacks_from_template(template))
        self.assertEqual(expected_routes, provider.routes)

    def test_with_quick_create_defined_route(self):
        expected_routes = [
            Route(
                path="/path1",
                methods=["GET"],
                function_name="SamFunc1",
            )
        ]

        template = {
            "Resources": {
                "Api1": {
                    "Type": "AWS::ApiGatewayV2::Api",
                    "Properties": {
                        "Target": "arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east-1"
                        ":123456789012:function:SamFunc1/invocations",
                        "RouteKey": "GET /path1",
                        "ProtocolType": "HTTP",
                    },
                }
            }
        }

        provider = ApiProvider(make_mock_stacks_from_template(template))
        self.assertEqual(expected_routes, provider.routes)

    def test_with_cors(self):
        expected_cors = Cors(
            allow_origin="https://example.com",
            allow_methods="GET,OPTIONS",
            allow_headers="x-apigateway-header",
            max_age=600,
        )

        template = {
            "Resources": {
                "Api1": {
                    "Type": "AWS::ApiGatewayV2::Api",
                    "Properties": {
                        "CorsConfiguration": {
                            "AllowHeaders": ["x-apigateway-header"],
                            "AllowMethods": ["GET"],
                            "AllowOrigins": ["https://example.com"],
                            "MaxAge": 600,
                        }
                    },
                }
            }
        }

        provider = ApiProvider(make_mock_stacks_from_template(template))
        self.assertEqual(expected_cors, provider.api.cors)


class TestCloudFormationProviderWithApiGatewayV2Route(TestCase):
    def test_basic_http_api_routes(self):
        template = {
            "Resources": {
                "TestHttpApi": {
                    "Type": "AWS::ApiGatewayV2::Api",
                    "Properties": {"name": "testHttpApi", "ProtocolType": "HTTP"},
                },
                "HttpApiRoute": {
                    "Type": "AWS::ApiGatewayV2::Route",
                    "Properties": {
                        "ApiId": "TestHttpApi",
                        "RouteKey": "POST /{proxy+}",
                        "Target": "integrations/HttpApiIntegration",
                    },
                },
                "HttpApiIntegration": {
                    "Type": "AWS::ApiGatewayV2::Integration",
                    "Properties": {
                        "ApiId": "TestHttpApi",
                        "PayloadFormatVersion": "2.0",
                        "IntegrationUri": "arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/"
                        "arn:aws:lambda:us-east-1:123456789012:function:SamFunc1/invocations",
                    },
                },
            }
        }

        provider = ApiProvider(make_mock_stacks_from_template(template))

        self.assertEqual(provider.routes, [Route(function_name="SamFunc1", path="/{proxy+}", methods=["POST"])])

    def test_http_api_routes_no_integration(self):
        template = {
            "Resources": {
                "TestHttpApi": {
                    "Type": "AWS::ApiGatewayV2::Api",
                    "Properties": {"name": "testHttpApi", "ProtocolType": "HTTP"},
                },
                "HttpApiRoute": {
                    "Type": "AWS::ApiGatewayV2::Route",
                    "Properties": {"ApiId": "TestHttpApi", "RouteKey": "POST /{proxy+}"},
                },
            }
        }

        provider = ApiProvider(make_mock_stacks_from_template(template))

        self.assertEqual(provider.routes, [])

    def test_http_api_default_route(self):
        template = {
            "Resources": {
                "TestHttpApi": {
                    "Type": "AWS::ApiGatewayV2::Api",
                    "Properties": {"name": "testHttpApi", "ProtocolType": "HTTP"},
                },
                "HttpApiRoute": {
                    "Type": "AWS::ApiGatewayV2::Route",
                    "Properties": {
                        "ApiId": "TestHttpApi",
                        "RouteKey": "$default",
                        "Target": "integrations/HttpApiIntegration",
                    },
                },
                "HttpApiIntegration": {
                    "Type": "AWS::ApiGatewayV2::Integration",
                    "Properties": {
                        "ApiId": "TestHttpApi",
                        "PayloadFormatVersion": "2.0",
                        "IntegrationUri": "arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/"
                        "arn:aws:lambda:us-east-1:123456789012:function:SamFunc1/invocations",
                    },
                },
            }
        }

        provider = ApiProvider(make_mock_stacks_from_template(template))

        self.assertEqual(
            provider.routes,
            [Route(function_name="SamFunc1", path="$default", methods=["X-AMAZON-APIGATEWAY-ANY-METHOD"])],
        )

    def test_http_api_wrong_route(self):
        template = {
            "Resources": {
                "TestHttpApi": {
                    "Type": "AWS::ApiGatewayV2::Api",
                    "Properties": {"name": "testHttpApi", "ProtocolType": "HTTP"},
                },
                "HttpApiRoute": {
                    "Type": "AWS::ApiGatewayV2::Route",
                    "Properties": {
                        "ApiId": "TestHttpApi",
                        "RouteKey": "GET",
                        "Target": "integrations/HttpApiIntegration",
                    },
                },
                "HttpApiIntegration": {
                    "Type": "AWS::ApiGatewayV2::Integration",
                    "Properties": {
                        "ApiId": "TestHttpApi",
                        "PayloadFormatVersion": "2.0",
                        "IntegrationUri": "arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/"
                        "arn:aws:lambda:us-east-1:123456789012:function:SamFunc1/invocations",
                    },
                },
            }
        }

        self.assertRaises(Exception, ApiProvider, template)


class TestCloudFormationWithApiGatewayV2Stage(TestCase):
    def test_provider_parse_stage_name(self):
        template = {
            "Resources": {
                "Stage": {"Type": "AWS::ApiGatewayV2::Stage", "Properties": {"StageName": "dev", "ApiId": "TestApi"}},
                "TestApi": {
                    "Type": "AWS::ApiGatewayV2::Api",
                    "Properties": {
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
                        }
                    },
                },
            }
        }
        provider = ApiProvider(make_mock_stacks_from_template(template))
        route1 = Route(path="/path", methods=["GET"], function_name="NoApiEventFunction")

        self.assertIn(route1, provider.routes)
        self.assertEqual(provider.api.stage_name, "dev")
        self.assertEqual(provider.api.stage_variables, None)

    def test_provider_stage_variables(self):
        template = {
            "Resources": {
                "Stage": {
                    "Type": "AWS::ApiGatewayV2::Stage",
                    "Properties": {
                        "StageName": "dev",
                        "Variables": {"vis": "data", "random": "test", "foo": "bar"},
                        "ApiId": "TestApi",
                    },
                },
                "TestApi": {
                    "Type": "AWS::ApiGatewayV2::Api",
                    "Properties": {
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
                        }
                    },
                },
            }
        }
        provider = ApiProvider(make_mock_stacks_from_template(template))
        route1 = Route(path="/path", methods=["GET"], function_name="NoApiEventFunction")
        self.assertIn(route1, provider.routes)
        self.assertEqual(provider.api.stage_name, "dev")
        self.assertEqual(provider.api.stage_variables, {"vis": "data", "random": "test", "foo": "bar"})

    def test_multi_stage_get_all(self):
        resources = OrderedDict(
            {
                "ProductionApi": {
                    "Type": "AWS::ApiGatewayV2::Api",
                    "Properties": {
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
                                },
                                "/anotherpath": {
                                    "post": {
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
                                },
                            }
                        }
                    },
                }
            }
        )
        resources["StageDev"] = {
            "Type": "AWS::ApiGatewayV2::Stage",
            "Properties": {
                "StageName": "dev",
                "Variables": {"vis": "data", "random": "test", "foo": "bar"},
                "ApiId": "ProductionApi",
            },
        }
        resources["StageProd"] = {
            "Type": "AWS::ApiGatewayV2::Stage",
            "Properties": {
                "StageName": "Production",
                "Variables": {"vis": "prod data", "random": "test", "foo": "bar"},
                "ApiId": "ProductionApi",
            },
        }
        template = {"Resources": resources}
        provider = ApiProvider(make_mock_stacks_from_template(template))

        result = [f for f in provider.get_all()]
        routes = result[0].routes

        route1 = Route(path="/path", methods=["GET"], function_name="NoApiEventFunction")
        route2 = Route(path="/anotherpath", methods=["POST"], function_name="NoApiEventFunction")
        self.assertEqual(len(routes), 2)
        self.assertIn(route1, routes)
        self.assertIn(route2, routes)

        self.assertEqual(provider.api.stage_name, "Production")
        self.assertEqual(provider.api.stage_variables, {"vis": "prod data", "random": "test", "foo": "bar"})
