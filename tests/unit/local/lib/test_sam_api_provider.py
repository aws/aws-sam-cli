from unittest import TestCase

from samcli.commands.local.lib.provider import Api
from samcli.commands.local.lib.sam_api_provider import SamApiProvider


class TestSamStageValues(TestCase):

    def test_provider_parse_stage_name(self):
        template = {
            "Resources": {

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
        provider = SamApiProvider(template)
        api1 = Api(path='/path', method='GET', function_name='NoApiEventFunction', cors=None, binary_media_types=[],
                   stage_name='dev',
                   stage_variables=None)

        self.assertIn(api1, provider.apis)

    def test_provider_stage_variables(self):
        template = {
            "Resources": {

                "TestApi": {
                    "Type": "AWS::Serverless::Api",
                    "Properties": {
                        "StageName": "dev",
                        "Variables": {
                            "vis": "data",
                            "random": "test",
                            "foo": "bar"
                        },
                        "DefinitionBody": {
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
        provider = SamApiProvider(template)
        api1 = Api(path='/path', method='GET', function_name='NoApiEventFunction', cors=None, binary_media_types=[],
                   stage_name='dev',
                   stage_variables={
                       "vis": "data",
                       "random": "test",
                       "foo": "bar"
                   })

        self.assertIn(api1, provider.apis)

    def test_multi_stage_get_all(self):
        template = {
            "Resources": {
                "TestApi": {
                    "Type": "AWS::Serverless::Api",
                    "Properties": {
                        "StageName": "dev",
                        "Variables": {
                            "vis": "data",
                            "random": "test",
                            "foo": "bar"
                        },
                        "DefinitionBody": {
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
                },
                "ProductionApi": {
                    "Type": "AWS::Serverless::Api",
                    "Properties": {
                        "StageName": "Production",
                        "Variables": {
                            "vis": "prod data",
                            "random": "test",
                            "foo": "bar"
                        },
                        "DefinitionBody": {
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
            }
        }

        provider = SamApiProvider(template)

        result = [f for f in provider.get_all()]

        api1 = Api(path='/path2', method='GET', function_name='NoApiEventFunction', cors=None, binary_media_types=[],
                   stage_name='dev',
                   stage_variables={
                       "vis": "data",
                       "random": "test",
                       "foo": "bar"
                   })
        api2 = Api(path='/path', method='GET', function_name='NoApiEventFunction', cors=None, binary_media_types=[],
                   stage_name='Production', stage_variables={'vis': 'prod data', 'random': 'test', 'foo': 'bar'})
        api3 = Api(path='/anotherpath', method='POST', function_name='NoApiEventFunction', cors=None,
                   binary_media_types=[],
                   stage_name='Production',
                   stage_variables={
                       "vis": "prod data",
                       "random": "test",
                       "foo": "bar"
                   })
        self.assertEquals(len(result), 3)
        self.assertIn(api1, result)
        self.assertIn(api2, result)
        self.assertIn(api3, result)
