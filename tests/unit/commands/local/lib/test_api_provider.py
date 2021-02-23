from collections import OrderedDict
from unittest import TestCase

from unittest.mock import patch, Mock

from samcli.lib.providers.provider import Api
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
