import json
import tempfile
from collections import OrderedDict
from unittest import TestCase

from mock import patch
from six import assertCountEqual

from samcli.commands.local.lib.cfn_api_provider import CfnApiProvider
from samcli.commands.local.lib.api_provider import ApiProvider
from samcli.local.apigw.local_apigw_service import Route
from tests.unit.commands.local.lib.test_sam_api_provider import make_swagger


class TestApiProviderWithApiGatewayRestRoute(TestCase):

    def setUp(self):
        self.binary_types = ["image/png", "image/jpg"]
        self.input_routes = [
            Route(path="/path1", method="GET", function_name="SamFunc1"),
            Route(path="/path1", method="POST", function_name="SamFunc1"),

            Route(path="/path2", method="PUT", function_name="SamFunc1"),
            Route(path="/path2", method="GET", function_name="SamFunc1"),

            Route(path="/path3", method="DELETE", function_name="SamFunc1")
        ]

    def test_with_no_apis(self):
        template = {
            "Resources": {

                "Api1": {
                    "Type": "AWS::ApiGateway::RestApi",
                    "Properties": {
                    },

                }
            }
        }

        provider = ApiProvider(template)

        self.assertEquals(provider.routes, [])

    def test_with_inline_swagger_apis(self):
        template = {
            "Resources": {

                "Api1": {
                    "Type": "AWS::ApiGateway::RestApi",
                    "Properties": {
                        "Body": make_swagger(self.input_routes)
                    }
                }
            }
        }

        provider = ApiProvider(template)
        assertCountEqual(self, self.input_routes, provider.routes)

    def test_with_swagger_as_local_file(self):
        with tempfile.NamedTemporaryFile(mode='w') as fp:
            filename = fp.name

            swagger = make_swagger(self.input_routes)
            json.dump(swagger, fp)
            fp.flush()

            template = {
                "Resources": {

                    "Api1": {
                        "Type": "AWS::ApiGateway::RestApi",
                        "Properties": {
                            "BodyS3Location": filename
                        }
                    }
                }
            }

            provider = ApiProvider(template)
            assertCountEqual(self, self.input_routes, provider.routes)

    def test_body_with_swagger_as_local_file_expect_fail(self):
        with tempfile.NamedTemporaryFile(mode='w') as fp:
            filename = fp.name

            swagger = make_swagger(self.input_routes)
            json.dump(swagger, fp)
            fp.flush()

            template = {
                "Resources": {

                    "Api1": {
                        "Type": "AWS::ApiGateway::RestApi",
                        "Properties": {
                            "Body": filename
                        }
                    }
                }
            }
            self.assertRaises(Exception, ApiProvider, template)

    @patch("samcli.commands.local.lib.cfn_base_api_provider.SwaggerReader")
    def test_with_swagger_as_both_body_and_uri_called(self, SwaggerReaderMock):
        body = {"some": "body"}
        filename = "somefile.txt"

        template = {
            "Resources": {

                "Api1": {
                    "Type": "AWS::ApiGateway::RestApi",
                    "Properties": {
                        "BodyS3Location": filename,
                        "Body": body
                    }
                }
            }
        }

        SwaggerReaderMock.return_value.read.return_value = make_swagger(self.input_routes)

        cwd = "foo"
        provider = ApiProvider(template, cwd=cwd)
        assertCountEqual(self, self.input_routes, provider.routes)
        SwaggerReaderMock.assert_called_with(definition_body=body, definition_uri=filename, working_dir=cwd)

    def test_swagger_with_any_method(self):
        routes = [
            Route(path="/path", method="any", function_name="SamFunc1")
        ]

        expected_routes = [
            Route(path="/path", method="GET", function_name="SamFunc1"),
            Route(path="/path", method="POST", function_name="SamFunc1"),
            Route(path="/path", method="PUT", function_name="SamFunc1"),
            Route(path="/path", method="DELETE", function_name="SamFunc1"),
            Route(path="/path", method="HEAD", function_name="SamFunc1"),
            Route(path="/path", method="OPTIONS", function_name="SamFunc1"),
            Route(path="/path", method="PATCH", function_name="SamFunc1")
        ]

        template = {
            "Resources": {
                "Api1": {
                    "Type": "AWS::ApiGateway::RestApi",
                    "Properties": {
                        "Body": make_swagger(routes)
                    }
                }
            }
        }

        provider = ApiProvider(template)
        assertCountEqual(self, expected_routes, provider.routes)

    def test_with_binary_media_types(self):
        template = {
            "Resources": {

                "Api1": {
                    "Type": "AWS::ApiGateway::RestApi",
                    "Properties": {
                        "Body": make_swagger(self.input_routes, binary_media_types=self.binary_types)
                    }
                }
            }
        }

        expected_binary_types = sorted(self.binary_types)
        expected_apis = [
            Route(path="/path1", method="GET", function_name="SamFunc1"),
            Route(path="/path1", method="POST", function_name="SamFunc1"),
            Route(path="/path2", method="PUT", function_name="SamFunc1"),
            Route(path="/path2", method="GET", function_name="SamFunc1"),

            Route(path="/path3", method="DELETE", function_name="SamFunc1")
        ]

        provider = ApiProvider(template)
        assertCountEqual(self, expected_apis, provider.routes)
        assertCountEqual(self, provider.api.get_binary_media_types(), expected_binary_types)

    def test_with_binary_media_types_in_swagger_and_on_resource(self):
        input_routes = [
            Route(path="/path", method="OPTIONS", function_name="SamFunc1"),
        ]
        extra_binary_types = ["text/html"]

        template = {
            "Resources": {

                "Api1": {
                    "Type": "AWS::ApiGateway::RestApi",
                    "Properties": {
                        "BinaryMediaTypes": extra_binary_types,
                        "Body": make_swagger(input_routes, binary_media_types=self.binary_types)
                    }
                }
            }
        }

        expected_binary_types = sorted(self.binary_types + extra_binary_types)
        expected_routes = [
            Route(path="/path", method="OPTIONS", function_name="SamFunc1"),
        ]

        provider = ApiProvider(template)
        assertCountEqual(self, expected_routes, provider.routes)
        assertCountEqual(self, provider.api.get_binary_media_types(), expected_binary_types)


class TestCloudFormationStageValues(TestCase):

    def test_provider_parse_stage_name(self):
        template = {
            "Resources": {
                "Stage": {
                    "Type": "AWS::ApiGateway::Stage",
                    "Properties": {
                        "StageName": "dev",
                        "RestApiId": "TestApi"
                    }
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
                                                           "/functions/${NoApiEventFunction.Arn}/invocations",
                                            },
                                            "responses": {},
                                        },
                                    }
                                }

                            }
                        }
                    }
                }
            }
        }
        provider = ApiProvider(template)
        route1 = Route(path='/path', method='GET', function_name='NoApiEventFunction')

        self.assertIn(route1, provider.routes)
        self.assertEquals(provider.api.stage_name, "dev")
        self.assertEquals(provider.api.stage_variables, None)

    def test_provider_stage_variables(self):
        template = {
            "Resources": {
                "Stage": {
                    "Type": "AWS::ApiGateway::Stage",
                    "Properties": {
                        "StageName": "dev",
                        "Variables": {
                            "vis": "data",
                            "random": "test",
                            "foo": "bar"
                        },
                        "RestApiId": "TestApi"
                    }
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
                                                           "/functions/${NoApiEventFunction.Arn}/invocations",
                                            },
                                            "responses": {},
                                        },
                                    }
                                }

                            }
                        }
                    }
                }
            }
        }
        provider = ApiProvider(template)
        route1 = Route(path='/path', method='GET', function_name='NoApiEventFunction')
        self.assertIn(route1, provider.routes)
        self.assertEquals(provider.api.stage_name, "dev")
        self.assertEquals(provider.api.stage_variables, {
            "vis": "data",
            "random": "test",
            "foo": "bar"
        })

    def test_multi_stage_get_all(self):
        template = OrderedDict({
            "Resources": {}
        })
        template["Resources"]["StageDev"] = {
            "Type": "AWS::ApiGateway::Stage",
            "Properties": {
                "StageName": "dev",
                "Variables": {
                    "vis": "data",
                    "random": "test",
                    "foo": "bar"
                },
                "RestApiId": "TestApi"
            }
        }
        template["Resources"]["StageProd"] = {
            "Type": "AWS::ApiGateway::Stage",
            "Properties": {
                "StageName": "Production",
                "Variables": {
                    "vis": "prod data",
                    "random": "test",
                    "foo": "bar"
                },
                "RestApiId": "ProductionApi"
            },
        }
        template["Resources"]["TestApi"] = {
            "Type": "AWS::ApiGateway::RestApi",
            "Properties": {
                "Body": {
                    "paths": {
                        "/path2": {
                            "get": {
                                "x-amazon-apigateway-integration": {
                                    "httpMethod": "POST",
                                    "type": "aws_proxy",
                                    "uri": {
                                        "Fn::Sub": "arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31"
                                                   "/functions/${NoApiEventFunction.Arn}/invocations",
                                    },
                                    "responses": {},
                                },
                            }
                        }
                    }
                }
            }
        }
        template["Resources"]["ProductionApi"] = {
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
                                                   "/functions/${NoApiEventFunction.Arn}/invocations",
                                    },
                                    "responses": {},
                                },
                            }
                        },
                        "/anotherpath": {
                            "post": {
                                "x-amazon-apigateway-integration": {
                                    "httpMethod": "POST",
                                    "type": "aws_proxy",
                                    "uri": {
                                        "Fn::Sub": "arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31"
                                                   "/functions/${NoApiEventFunction.Arn}/invocations",
                                    },
                                    "responses": {},
                                },
                            }
                        }

                    }
                }
            }
        }

        provider = ApiProvider(template)

        result = [f for f in provider.get_all()]

        route1 = Route(path='/path2', method='GET', function_name='NoApiEventFunction')
        route2 = Route(path='/path', method='GET', function_name='NoApiEventFunction')
        route3 = Route(path='/anotherpath', method='POST', function_name='NoApiEventFunction')
        self.assertEquals(len(result), 3)
        self.assertIn(route1, result)
        self.assertIn(route2, result)
        self.assertIn(route3, result)
        self.assertEquals(provider.api.stage_name, "Production")
        self.assertEquals(provider.api.stage_variables, {
            "vis": "prod data",
            "random": "test",
            "foo": "bar"
        })


class TestCloudFormationResourceMethod(TestCase):

    def setUp(self):
        self.binary_types = ["image/png", "image/jpg"]
        self.input_routes = [
            Route(path="/path1", method="GET", function_name="SamFunc1"),
            Route(path="/path1", method="POST", function_name="SamFunc1"),

            Route(path="/path2", method="PUT", function_name="SamFunc1"),
            Route(path="/path2", method="GET", function_name="SamFunc1"),

            Route(path="/path3", method="DELETE", function_name="SamFunc1")
        ]

    def test_basic_rest_api_resource_method(self):
        template = {
            "Resources": {
                "TestApi": {
                    "Type": "AWS::ApiGateway::RestApi",
                    "Properties": {
                        "StageName": "Prod"
                    }
                },
                "ApiResource": {
                    "Properties": {
                        "PathPart": "{proxy+}",
                        "RestApiId": "TestApi",
                    }
                },
                "ApiMethod": {
                    "Type": "AWS::ApiGateway::Method",
                    "Properties": {
                        "HttpMethod": "POST",
                        "RestApiId": "TestApi",
                        "ResourceId": "ApiResource"
                    },
                }
            }
        }

        provider = ApiProvider(template)

        self.assertEquals(provider.routes, [Route(function_name=None, path="/{proxy+}", method="POST")])

    def test_resolve_correct_resource_path(self):
        resources = {
            "RootApiResource": {
                "Tyoe": "AWS::ApiGateway::Resource",
                "Properties": {
                    "PathPart": "root",
                    "ResourceId": "TestApi",
                }
            }
        }
        beta_resource = {
            "Tyoe": "AWS::ApiGateway::Resource",
            "Properties": {
                "PathPart": "beta",
                "ResourceId": "TestApi",
                "ParentId": "RootApiResource"
            }
        }
        resources["BetaApiResource"] = beta_resource
        provider = CfnApiProvider()
        full_path = provider.resolve_resource_path(resources, beta_resource, "/test")
        self.assertEquals(full_path, "/root/beta/test")

    def test_resolve_correct_multi_parent_resource_path(self):
        template = {
            "Resources": {
                "TestApi": {
                    "Type": "AWS::ApiGateway::Resource",
                    "Properties": {
                        "StageName": "Prod"
                    }
                },
                "RootApiResource": {
                    "Type": "AWS::ApiGateway::Resource",
                    "Properties": {
                        "PathPart": "root",
                        "ResourceId": "TestApi",
                    }
                },
                "V1ApiResource": {
                    "Type": "AWS::ApiGateway::Resource",
                    "Properties": {
                        "PathPart": "v1",
                        "ResourceId": "TestApi",
                        "ParentId": "RootApiResource"
                    }
                },
                "AlphaApiResource": {
                    "Type": "AWS::ApiGateway::Resource",
                    "Properties": {
                        "PathPart": "alpha",
                        "ResourceId": "TestApi",
                        "ParentId": "V1ApiResource"
                    }
                },
                "BetaApiResource": {
                    "Type": "AWS::ApiGateway::Resource",
                    "Properties": {
                        "PathPart": "beta",
                        "ResourceId": "TestApi",
                        "ParentId": "V1ApiResource"
                    }
                },
                "AlphaApiMethod": {
                    "Type": "AWS::ApiGateway::Method",
                    "Properties": {
                        "HttpMethod": "GET",
                        "RestApiId": "TestApi",
                        "ResourceId": "AlphaApiResource"
                    },
                },
                "BetaAlphaApiMethod": {
                    "Type": "AWS::ApiGateway::Method",
                    "Properties": {
                        "HttpMethod": "POST",
                        "RestApiId": "TestApi",
                        "ResourceId": "BetaApiResource"
                    },
                }
            }
        }

        provider = ApiProvider(template)
        assertCountEqual(self, provider.routes, [Route(path="/root/v1/beta", method="POST", function_name=None),
                                                 Route(path="/root/v1/alpha", method="GET", function_name=None)])

    def test_resource_with_method_correct_routes(self):
        template = {
            "Resources": {
                "TestApi": {
                    "Type": "AWS::ApiGateway::Resource",
                    "Properties": {
                        "StageName": "Prod"
                    }
                },
                "BetaApiResource": {
                    "Type": "AWS::ApiGateway::Resource",
                    "Properties": {
                        "PathPart": "beta",
                        "ResourceId": "TestApi",
                    }
                },
                "BetaAlphaApiMethod": {
                    "Type": "AWS::ApiGateway::Method",
                    "Properties": {
                        "HttpMethod": "ANY",
                        "RestApiId": "TestApi",
                        "ResourceId": "BetaApiResource",
                    },
                }
            }
        }
        provider = ApiProvider(template)
        assertCountEqual(self, provider.routes,
                         [Route(path="/beta", method="POST", function_name=None),
                          Route(path="/beta", method="GET", function_name=None),
                          Route(path="/beta", method="DELETE", function_name=None),
                          Route(path="/beta", method="HEAD", function_name=None),
                          Route(path="/beta", method="OPTIONS", function_name=None),
                          Route(path="/beta", method="PATCH", function_name=None),
                          Route(path="/beta", method="PUT", function_name=None),
                          ])

    def test_method_integration_uri(self):
        template = {
            "Resources": {
                "TestApi": {
                    "Type": "AWS::ApiGateway::Resource",
                    "Properties": {
                        "StageName": "Prod"
                    }
                },
                "RootApiResource": {
                    "Type": "AWS::ApiGateway::Resource",
                    "Properties": {
                        "PathPart": "root",
                        "ResourceId": "TestApi",
                    }
                },
                "V1ApiResource": {
                    "Type": "AWS::ApiGateway::Resource",
                    "Properties": {
                        "PathPart": "v1",
                        "ResourceId": "TestApi",
                        "ParentId": "RootApiResource"
                    }
                },
                "AlphaApiResource": {
                    "Type": "AWS::ApiGateway::Resource",
                    "Properties": {
                        "PathPart": "alpha",
                        "ResourceId": "TestApi",
                        "ParentId": "V1ApiResource"
                    }
                },
                "BetaApiResource": {
                    "Type": "AWS::ApiGateway::Resource",
                    "Properties": {
                        "PathPart": "beta",
                        "ResourceId": "TestApi",
                        "ParentId": "V1ApiResource"
                    }
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
                        }
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
                        }
                    },
                },
                "AWSAlphaLambdaFunction": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {
                        "Code": ".",
                        "Handler": "main.run_test",
                        "Runtime": "Python3.6"
                    }
                },
                "AWSBetaLambdaFunction": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {
                        "Code": ".",
                        "Handler": "main.run_test",
                        "Runtime": "Python3.6"
                    }
                }
            }
        }

        provider = ApiProvider(template)
        assertCountEqual(self, provider.routes,
                         [Route(path="/root/v1/beta", method="POST", function_name="AWSLambdaFunction"),
                          Route(path="/root/v1/alpha", method="GET", function_name="AWSBetaLambdaFunction")])

    def test_binary_media_types_method(self):
        template = {
            "Resources": {
                "TestApi": {
                    "Type": "AWS::ApiGateway::Resource",
                    "Properties": {
                        "StageName": "Prod"
                    }
                },
                "RootApiResource": {
                    "Type": "AWS::ApiGateway::Resource",
                    "Properties": {
                        "PathPart": "root",
                        "ResourceId": "TestApi",
                    }
                },
                "V1ApiResource": {
                    "Type": "AWS::ApiGateway::Resource",
                    "Properties": {
                        "PathPart": "v1",
                        "ResourceId": "TestApi",
                        "ParentId": "RootApiResource"
                    }
                },
                "AlphaApiResource": {
                    "Type": "AWS::ApiGateway::Resource",
                    "Properties": {
                        "PathPart": "alpha",
                        "ResourceId": "TestApi",
                        "ParentId": "V1ApiResource"
                    }
                },
                "BetaApiResource": {
                    "Type": "AWS::ApiGateway::Resource",
                    "Properties": {
                        "PathPart": "beta",
                        "ResourceId": "TestApi",
                        "ParentId": "V1ApiResource"
                    }
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
                            "ContentType": "image~1jpg"
                        }
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
                            "ContentType": "image~1png"
                        }
                    },
                },
                "AWSAlphaLambdaFunction": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {
                        "Code": ".",
                        "Handler": "main.run_test",
                        "Runtime": "Python3.6"
                    }
                },
                "AWSBetaLambdaFunction": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {
                        "Code": ".",
                        "Handler": "main.run_test",
                        "Runtime": "Python3.6"
                    }
                }
            }
        }

        provider = ApiProvider(template)
        assertCountEqual(self, provider.api.get_binary_media_types(), ["image/png", "image/jpg"])

    def test_cdk(self):
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Resources": {
                "HelloHandlerServiceRole11EF7C63": {
                    "Type": "AWS::IAM::Role",
                    "Properties": {
                        "AssumeRolePolicyDocument": {
                            "Statement": [
                                {
                                    "Action": "sts:AssumeRole",
                                    "Effect": "Allow",
                                    "Principal": {
                                        "Service": "lambda.amazonaws.com"
                                    }
                                }
                            ],
                            "Version": "2012-10-17"
                        },
                        "ManagedPolicyArns": [
                            {
                                "Fn::Join": [
                                    "",
                                    [
                                        "arn:",
                                        {
                                            "Ref": "AWS::Partition"
                                        },
                                        "iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
                                    ]
                                ]
                            }
                        ]
                    },
                    "Metadata": {
                        "aws:cdk:path": "CdkWorkshopStack/HelloHandler/ServiceRole/Resource"
                    }
                },
                "HelloHandler2E4FBA4D": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {
                        "Code": ".",
                        "Handler": "main.handler",
                        "Role": {
                            "Fn::GetAtt": [
                                "HelloHandlerServiceRole11EF7C63",
                                "Arn"
                            ]
                        },
                        "Runtime": "nodejs8.10"
                    },
                    "DependsOn": [
                        "HelloHandlerServiceRole11EF7C63"
                    ],
                    "Metadata": {
                        "aws:cdk:path": "CdkWorkshopStack/HelloHandler/Resource",
                        "aws:asset:path": "/Users/viksriva/Documents/cdk-workshop/lambda",
                        "aws:asset:property": "Code"
                    }
                },
                "HelloHandlerApiPermissionANYAC4E141E": {
                    "Type": "AWS::Lambda::Permission",
                    "Properties": {
                        "Action": "lambda:InvokeFunction",
                        "FunctionName": {
                            "Ref": "HelloHandler2E4FBA4D"
                        },
                        "Principal": "apigateway.amazonaws.com",
                        "SourceArn": {
                            "Fn::Join": [
                                "",
                                [
                                    "arn:",
                                    {
                                        "Ref": "AWS::Partition"
                                    },
                                    ":execute-api:",
                                    {
                                        "Ref": "AWS::Region"
                                    },
                                    ":",
                                    {
                                        "Ref": "AWS::AccountId"
                                    },
                                    ":",
                                    {
                                        "Ref": "EndpointEEF1FD8F"
                                    },
                                    "/",
                                    {
                                        "Ref": "EndpointDeploymentStageprodB78BEEA0"
                                    },
                                    "/*/"
                                ]
                            ]
                        }
                    },
                    "Metadata": {
                        "aws:cdk:path": "CdkWorkshopStack/HelloHandler/ApiPermission.ANY.."
                    }
                },
                "HelloHandlerApiPermissionTestANYDDD56D72": {
                    "Type": "AWS::Lambda::Permission",
                    "Properties": {
                        "Action": "lambda:InvokeFunction",
                        "FunctionName": {
                            "Ref": "HelloHandler2E4FBA4D"
                        },
                        "Principal": "apigateway.amazonaws.com",
                        "SourceArn": {
                            "Fn::Join": [
                                "",
                                [
                                    "arn:",
                                    {
                                        "Ref": "AWS::Partition"
                                    },
                                    ":execute-api:",
                                    {
                                        "Ref": "AWS::Region"
                                    },
                                    ":",
                                    {
                                        "Ref": "AWS::AccountId"
                                    },
                                    ":",
                                    {
                                        "Ref": "EndpointEEF1FD8F"
                                    },
                                    "/test-invoke-stage/*/"
                                ]
                            ]
                        }
                    },
                    "Metadata": {
                        "aws:cdk:path": "CdkWorkshopStack/HelloHandler/ApiPermission.Test.ANY.."
                    }
                },
                "HelloHandlerApiPermissionANYproxy90E90CD6": {
                    "Type": "AWS::Lambda::Permission",
                    "Properties": {
                        "Action": "lambda:InvokeFunction",
                        "FunctionName": {
                            "Ref": "HelloHandler2E4FBA4D"
                        },
                        "Principal": "apigateway.amazonaws.com",
                        "SourceArn": {
                            "Fn::Join": [
                                "",
                                [
                                    "arn:",
                                    {
                                        "Ref": "AWS::Partition"
                                    },
                                    ":execute-api:",
                                    {
                                        "Ref": "AWS::Region"
                                    },
                                    ":",
                                    {
                                        "Ref": "AWS::AccountId"
                                    },
                                    ":",
                                    {
                                        "Ref": "EndpointEEF1FD8F"
                                    },
                                    "/",
                                    {
                                        "Ref": "EndpointDeploymentStageprodB78BEEA0"
                                    },
                                    "/*/{proxy+}"
                                ]
                            ]
                        }
                    },
                    "Metadata": {
                        "aws:cdk:path": "CdkWorkshopStack/HelloHandler/ApiPermission.ANY..{proxy+}"
                    }
                },
                "HelloHandlerApiPermissionTestANYproxy9803526C": {
                    "Type": "AWS::Lambda::Permission",
                    "Properties": {
                        "Action": "lambda:InvokeFunction",
                        "FunctionName": {
                            "Ref": "HelloHandler2E4FBA4D"
                        },
                        "Principal": "apigateway.amazonaws.com",
                        "SourceArn": {
                            "Fn::Join": [
                                "",
                                [
                                    "arn:",
                                    {
                                        "Ref": "AWS::Partition"
                                    },
                                    ":execute-api:",
                                    {
                                        "Ref": "AWS::Region"
                                    },
                                    ":",
                                    {
                                        "Ref": "AWS::AccountId"
                                    },
                                    ":",
                                    {
                                        "Ref": "EndpointEEF1FD8F"
                                    },
                                    "/test-invoke-stage/*/{proxy+}"
                                ]
                            ]
                        }
                    },
                    "Metadata": {
                        "aws:cdk:path": "CdkWorkshopStack/HelloHandler/ApiPermission.Test.ANY..{proxy+}"
                    }
                },
                "EndpointEEF1FD8F": {
                    "Type": "AWS::ApiGateway::RestApi",
                    "Properties": {
                        "Name": "Endpoint"
                    },
                    "Metadata": {
                        "aws:cdk:path": "CdkWorkshopStack/Endpoint/Resource"
                    }
                },
                "EndpointDeployment318525DA37c0e38727e25b4317827bf43e918fbf": {
                    "Type": "AWS::ApiGateway::Deployment",
                    "Properties": {
                        "RestApiId": {
                            "Ref": "EndpointEEF1FD8F"
                        },
                        "Description": "Automatically created by the RestApi construct"
                    },
                    "DependsOn": [
                        "Endpointproxy39E2174E",
                        "EndpointANY485C938B",
                        "EndpointproxyANYC09721C5"
                    ],
                    "Metadata": {
                        "aws:cdk:path": "CdkWorkshopStack/Endpoint/Deployment/Resource"
                    }
                },
                "EndpointDeploymentStageprodB78BEEA0": {
                    "Type": "AWS::ApiGateway::Stage",
                    "Properties": {
                        "RestApiId": {
                            "Ref": "EndpointEEF1FD8F"
                        },
                        "DeploymentId": {
                            "Ref": "EndpointDeployment318525DA37c0e38727e25b4317827bf43e918fbf"
                        },
                        "StageName": "prod"
                    },
                    "Metadata": {
                        "aws:cdk:path": "CdkWorkshopStack/Endpoint/DeploymentStage.prod/Resource"
                    }
                },
                "EndpointCloudWatchRoleC3C64E0F": {
                    "Type": "AWS::IAM::Role",
                    "Properties": {
                        "AssumeRolePolicyDocument": {
                            "Statement": [
                                {
                                    "Action": "sts:AssumeRole",
                                    "Effect": "Allow",
                                    "Principal": {
                                        "Service": "apigateway.amazonaws.com"
                                    }
                                }
                            ],
                            "Version": "2012-10-17"
                        },
                        "ManagedPolicyArns": [
                            {
                                "Fn::Join": [
                                    "",
                                    [
                                        "arn:",
                                        {
                                            "Ref": "AWS::Partition"
                                        },
                                        "iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs"
                                    ]
                                ]
                            }
                        ]
                    },
                    "Metadata": {
                        "aws:cdk:path": "CdkWorkshopStack/Endpoint/CloudWatchRole/Resource"
                    }
                },
                "EndpointAccountB8304247": {
                    "Type": "AWS::ApiGateway::Account",
                    "Properties": {
                        "CloudWatchRoleArn": {
                            "Fn::GetAtt": [
                                "EndpointCloudWatchRoleC3C64E0F",
                                "Arn"
                            ]
                        }
                    },
                    "DependsOn": [
                        "EndpointEEF1FD8F"
                    ],
                    "Metadata": {
                        "aws:cdk:path": "CdkWorkshopStack/Endpoint/Account"
                    }
                },
                "Endpointproxy39E2174E": {
                    "Type": "AWS::ApiGateway::Resource",
                    "Properties": {
                        "ParentId": {
                            "Fn::GetAtt": [
                                "EndpointEEF1FD8F",
                                "RootResourceId"
                            ]
                        },
                        "PathPart": "{proxy+}",
                        "RestApiId": {
                            "Ref": "EndpointEEF1FD8F"
                        }
                    },
                    "Metadata": {
                        "aws:cdk:path": "CdkWorkshopStack/Endpoint/{proxy+}/Resource"
                    }
                },
                "EndpointproxyANYC09721C5": {
                    "Type": "AWS::ApiGateway::Method",
                    "Properties": {
                        "HttpMethod": "ANY",
                        "ResourceId": "!Ref Endpointproxy39E2174E",
                        "RestApiId": {
                            "Ref": "EndpointEEF1FD8F"
                        },
                        "AuthorizationType": "NONE",
                        "Integration": {
                            "IntegrationHttpMethod": "POST",
                            "Type": "AWS_PROXY",
                            "Uri": {
                                "Fn::Join": [
                                    "",
                                    [
                                        "arn:",
                                        {
                                            "Ref": "AWS::Partition"
                                        },
                                        ":apigateway:",
                                        {
                                            "Ref": "AWS::Region"
                                        },
                                        "lambda:path/2015-03-31/functions/",
                                        {
                                            "Fn::GetAtt": [
                                                "HelloHandler2E4FBA4D",
                                                "Arn"
                                            ]
                                        },
                                        "/invocations"
                                    ]
                                ]
                            }
                        }
                    },
                    "Metadata": {
                        "aws:cdk:path": "CdkWorkshopStack/Endpoint/{proxy+}/ANY/Resource"
                    }
                },
                "EndpointANY485C938B": {
                    "Type": "AWS::ApiGateway::Method",
                    "Properties": {
                        "HttpMethod": "ANY",
                        "ResourceId": {
                            "Fn::GetAtt": [
                                "EndpointEEF1FD8F",
                                "RootResourceId"
                            ]
                        },
                        "RestApiId": {
                            "Ref": "EndpointEEF1FD8F"
                        },
                        "AuthorizationType": "NONE",
                        "Integration": {
                            "IntegrationHttpMethod": "POST",
                            "Type": "AWS_PROXY",
                            "Uri": {
                                "Fn::Join": [
                                    "",
                                    [
                                        "arn:",
                                        {
                                            "Ref": "AWS::Partition"
                                        },
                                        ":apigateway:",
                                        {
                                            "Ref": "AWS::Region"
                                        },
                                        "lambda:path/2015-03-31/functions/",
                                        {
                                            "Fn::GetAtt": [
                                                "HelloHandler2E4FBA4D",
                                                "Arn"
                                            ]
                                        },
                                        "/invocations"
                                    ]
                                ]
                            }
                        }
                    },
                    "Metadata": {
                        "aws:cdk:path": "CdkWorkshopStack/Endpoint/ANY/Resource"
                    }
                },
                "CDKMetadata": {
                    "Type": "AWS::CDK::Metadata",
                    "Properties": {
                        "Modules": "aws-cdk=0.22.0,jsii-runtime=node.js/v12.4.0"
                    }
                }
            },
            "Parameters": {
                "HelloHandlerCodeS3Bucket4359A483": {
                    "Type": "String",
                    "Description": "S3 bucket for asset \"CdkWorkshopStack/HelloHandler/Code\""
                },
                "HelloHandlerCodeS3VersionKey07D12610": {
                    "Type": "String",
                    "Description": "S3 key for asset version \"CdkWorkshopStack/HelloHandler/Code\""
                }
            },
            "Outputs": {
                "Endpoint8024A810": {
                    "Value": {
                        "Fn::Join": [
                            "",
                            [
                                "https://",
                                {
                                    "Ref": "EndpointEEF1FD8F"
                                },
                                ".execute-api.",
                                {
                                    "Ref": "AWS::Region"
                                },
                                ".",
                                {
                                    "Ref": "AWS::URLSuffix"
                                },
                                "/",
                                {
                                    "Ref": "EndpointDeploymentStageprodB78BEEA0"
                                },
                                "/"
                            ]
                        ]
                    },
                    "Export": {
                        "Name": "CdkWorkshopStack:Endpoint8024A810"
                    }
                }
            }
        }
        provider = ApiProvider(template)
