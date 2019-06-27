from unittest import TestCase

from samcli.commands.local.lib.api_provider import ApiProvider
from samcli.local.apigw.local_apigw_service import Route


class TestSamApiProviderwithApiGatewayRestApi(TestCase):

    def setUp(self):
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
        provider = ApiProvider(template)
        route1 = Route(path='/path', method='GET', function_name='NoApiEventFunction')

        self.assertIn(route1, provider.routes)
        self.assertEquals(provider.api.stage_name, "dev")
        self.assertEquals(provider.api.stage_variables, None)

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
        template = {
            "Resources": {
                "StageDev": {
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
                "StageProd": {
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
                },
                "TestApi": {
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
                },
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
