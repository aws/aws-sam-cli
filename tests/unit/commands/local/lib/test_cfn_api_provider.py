import json
import tempfile
from collections import OrderedDict
from unittest import TestCase

from mock import patch
from six import assertCountEqual

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
