from unittest import TestCase
from unittest.mock import MagicMock, patch
from samcli.lib.sync.infra_sync_executor import InfraSyncExecutor
from botocore.exceptions import ClientError


class TestSyncFlowExecutor(TestCase):
    def setUp(self):
        self.template_dict = {
            "Resources": {
                "ServerlessFunction": {"Type": "AWS::Serverless::Function", "Properties": {"CodeUri": "local/"}}
            }
        }
        self.build_context = MagicMock()
        self.package_context = MagicMock()
        self.deploy_context = MagicMock()

    @patch("samcli.lib.sync.infra_sync_executor.is_local_path")
    @patch("samcli.lib.sync.infra_sync_executor.get_template_data")
    @patch("samcli.lib.sync.infra_sync_executor.Session")
    def test_compare_templates_basic(self, session_mock, get_template_mock, local_path_mock):
        get_template_mock.return_value = self.template_dict
        local_path_mock.return_value = True

        infra_sync_executor = InfraSyncExecutor(self.build_context, self.package_context, self.deploy_context)
        infra_sync_executor._cfn_client.get_template.return_value = {
            "TemplateBody": """{
                "Resources": {
                    "ServerlessFunction": {"Type": "AWS::Serverless::Function", "Properties": {"CodeUri": "local/"}}
                }
            }"""
        }

        self.assertTrue(infra_sync_executor._compare_templates("path", "stack_name"))

    @patch("samcli.lib.sync.infra_sync_executor.is_local_path")
    @patch("samcli.lib.sync.infra_sync_executor.get_template_data")
    @patch("samcli.lib.sync.infra_sync_executor.Session")
    def test_compare_templates_all_resources(self, session_mock, get_template_mock, local_path_mock):
        self.template_dict = {
            "Resources": {
                "ServerlessFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {"CodeUri": "local/", "ImageUri": "image"},
                },
                "LambdaFunction": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {
                        "Code": {
                            "ImageUri": "image",
                            "S3Bucket": "bucket",
                            "S3Key": "key",
                            "S3ObjectVersion": "version",
                        }
                    },
                },
                "ServerlessLayer": {"Type": "AWS::Serverless::LayerVersion", "Properties": {"ContentUri": "local/"}},
                "LambdaLayer": {"Type": "AWS::Lambda::LayerVersion", "Properties": {"Content": "local/"}},
                "ServerlessApi": {"Type": "AWS::Serverless::Api", "Properties": {"DefinitionBody": "definition"}},
                "RestApi": {"Type": "AWS::ApiGateway::RestApi", "Properties": {"BodyS3Location": "definiton"}},
                "ServerlessHttpApi": {"Type": "AWS::Serverless::HttpApi", "Properties": {"DefinitionUri": "definiton"}},
                "HttpApi": {"Type": "AWS::ApiGatewayV2::Api", "Properties": {"BodyS3Location": "definiton"}},
                "ServerlessStateMachine": {
                    "Type": "AWS::Serverless::StateMachine",
                    "Properties": {"DefinitionUri": "definiton"},
                },
                "StateMachine": {
                    "Type": "AWS::StepFunctions::StateMachine",
                    "Properties": {"DefinitionS3Location": "definiton"},
                },
            }
        }

        get_template_mock.return_value = self.template_dict
        local_path_mock.return_value = True

        infra_sync_executor = InfraSyncExecutor(self.build_context, self.package_context, self.deploy_context)
        infra_sync_executor._cfn_client.get_template.return_value = {
            "TemplateBody": """{
                "Resources": {
                    "ServerlessFunction": {
                        "Type": "AWS::Serverless::Function",
                        "Properties": {"CodeUri": "s3://location", "ImageUri": "s3://location"},
                    },
                    "LambdaFunction": {
                        "Type": "AWS::Lambda::Function",
                        "Properties": {
                            "Code": {
                                "ImageUri": "s3://location",
                                "S3Bucket": "s3://location",
                                "S3Key": "s3://location",
                                "S3ObjectVersion": "s3://location",
                            }
                        },
                    },
                    "ServerlessLayer": {
                        "Type": "AWS::Serverless::LayerVersion",
                        "Properties": {"ContentUri": "s3://location"},
                    },
                    "LambdaLayer": {"Type": "AWS::Lambda::LayerVersion", "Properties": {"Content": "s3://location"}},
                    "ServerlessApi": {"Type": "AWS::Serverless::Api", "Properties": {"DefinitionBody": "s3://location"}},
                    "RestApi": {"Type": "AWS::ApiGateway::RestApi", "Properties": {"BodyS3Location": "s3://location"}},
                    "ServerlessHttpApi": {
                        "Type": "AWS::Serverless::HttpApi",
                        "Properties": {"DefinitionUri": "s3://location"},
                    },
                    "HttpApi": {"Type": "AWS::ApiGatewayV2::Api", "Properties": {"BodyS3Location": "s3://location"}},
                    "ServerlessStateMachine": {
                        "Type": "AWS::Serverless::StateMachine",
                        "Properties": {"DefinitionUri": "s3://location"},
                    },
                    "StateMachine": {
                        "Type": "AWS::StepFunctions::StateMachine",
                        "Properties": {"DefinitionS3Location": "s3://location"},
                    },
                }
            }"""
        }

        self.assertTrue(infra_sync_executor._compare_templates("path", "stack_name"))

        local_path_mock.return_value = False
        self.assertFalse(infra_sync_executor._compare_templates("path", "stack_name"))

    @patch("samcli.lib.sync.infra_sync_executor.is_local_path")
    @patch("samcli.lib.sync.infra_sync_executor.get_template_data")
    @patch("samcli.lib.sync.infra_sync_executor.Session")
    def test_compare_templates_nested_stack(self, session_mock, get_template_mock, local_path_mock):
        self.template_dict = {
            "Resources": {
                "ServerlessApplication": {"Type": "AWS::Serverless::Application", "Properties": {"Location": "local/"}},
                "NestedStack": {"Type": "AWS::CloudFormation::Stack", "Properties": {"TemplateURL": "local/"}},
            }
        }

        self.nested_dict = {
            "Resources": {
                "ServerlessFunction": {"Type": "AWS::Serverless::Function", "Properties": {"CodeUri": "local/"}}
            }
        }

        get_template_mock.side_effect = [self.template_dict, self.nested_dict, self.nested_dict]
        local_path_mock.return_value = True

        infra_sync_executor = InfraSyncExecutor(self.build_context, self.package_context, self.deploy_context)
        infra_sync_executor._cfn_client.get_template.side_effect = [
            {
                "TemplateBody": """{
                    "Resources": {
                        "ServerlessApplication": {"Type": "AWS::Serverless::Application", "Properties": {"Location": "local/"}},
                        "NestedStack": {"Type": "AWS::CloudFormation::Stack", "Properties": {"TemplateURL": "local/"}},
                    }
                }"""
            },
            {
                "TemplateBody": """{
                    "Resources": {
                        "ServerlessFunction": {"Type": "AWS::Serverless::Function", "Properties": {"CodeUri": "local/"}}
                    }
                }"""
            },
            {
                "TemplateBody": """{
                    "Resources": {
                        "ServerlessFunction": {"Type": "AWS::Serverless::Function", "Properties": {"CodeUri": "local/"}}
                    }
                }"""
            },
        ]

        infra_sync_executor._cfn_client.describe_stack_resource.return_value = {
            "StackResourceDetails": {"PhysicalResourceId": "id"}
        }

        self.assertTrue(infra_sync_executor._compare_templates("path", "stack_name"))

    @patch("samcli.lib.sync.infra_sync_executor.is_local_path")
    @patch("samcli.lib.sync.infra_sync_executor.get_template_data")
    @patch("samcli.lib.sync.infra_sync_executor.Session")
    def test_compare_templates_http_template_location(self, session_mock, get_template_mock, local_path_mock):
        self.template_dict = {
            "Resources": {
                "ServerlessApplication": {
                    "Type": "AWS::Serverless::Application",
                    "Properties": {"Location": "https://s3.com/bucket/key"},
                }
            }
        }

        self.nested_dict = """{
            "Resources": {
                "ServerlessFunction": {"Type": "AWS::Serverless::Function", "Properties": {"CodeUri": "local/"}}
            }
        }"""

        get_template_mock.side_effect = [self.template_dict]
        local_path_mock.return_value = True

        infra_sync_executor = InfraSyncExecutor(self.build_context, self.package_context, self.deploy_context)
        infra_sync_executor._cfn_client.get_template.side_effect = [
            {
                "TemplateBody": """{
                    Resources: {
                        "ServerlessApplication": {
                            "Type": "AWS::Serverless::Application",
                            "Properties": {"Location": "https://s3.com/bucket/key"}
                        }
                    }
                }"""
            },
            {
                "TemplateBody": """{
                    "Resources": {
                        "ServerlessFunction": {"Type": "AWS::Serverless::Function", "Properties": {"CodeUri": "local/"}}
                    }
                }"""
            },
        ]

        infra_sync_executor._cfn_client.describe_stack_resource.return_value = {
            "StackResourceDetails": {"PhysicalResourceId": "id"}
        }

        with patch("botocore.response.StreamingBody") as stream_mock:
            stream_mock.read.return_value = self.nested_dict.encode("utf-8")
            infra_sync_executor._s3_client.get_object.return_value = {"Body": stream_mock}
            self.assertTrue(infra_sync_executor._compare_templates("path", "stack_name"))

    @patch("samcli.lib.sync.infra_sync_executor.is_local_path")
    @patch("samcli.lib.sync.infra_sync_executor.get_template_data")
    @patch("samcli.lib.sync.infra_sync_executor.Session")
    def test_compare_templates_exception(self, session_mock, get_template_mock, local_path_mock):
        self.template_dict = {
            "Resources": {
                "ServerlessApplication": {
                    "Type": "AWS::Serverless::Application",
                    "Properties": {"Location": "https://s3.com/bucket/key"},
                }
            }
        }

        get_template_mock.side_effect = [self.template_dict]
        local_path_mock.return_value = True

        infra_sync_executor = InfraSyncExecutor(self.build_context, self.package_context, self.deploy_context)
        infra_sync_executor._cfn_client.get_template.side_effect = [ClientError({"Error": {"Code": "404"}}, "Error")]

        self.assertFalse(infra_sync_executor._compare_templates("path", "stack_name"))

    @patch("samcli.lib.sync.infra_sync_executor.is_local_path")
    @patch("samcli.lib.sync.infra_sync_executor.Session")
    def test_remove_unnecessary_field(self, session_mock, local_path_mock):
        first_dict = {
            "Resources": {
                "ServerlessFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {"CodeUri": "local/", "ImageUri": "image"},
                },
                "LambdaFunction": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {
                        "Code": {
                            "ImageUri": "image",
                            "S3Bucket": "bucket",
                            "S3Key": "key",
                            "S3ObjectVersion": "version",
                        }
                    },
                },
                "ServerlessLayer": {"Type": "AWS::Serverless::LayerVersion", "Properties": {"ContentUri": "local/"}},
                "LambdaLayer": {"Type": "AWS::Lambda::LayerVersion", "Properties": {"Content": "local/"}},
                "ServerlessApi": {"Type": "AWS::Serverless::Api", "Properties": {"DefinitionBody": "definition"}},
                "RestApi": {"Type": "AWS::ApiGateway::RestApi", "Properties": {"BodyS3Location": "definiton"}},
                "ServerlessHttpApi": {"Type": "AWS::Serverless::HttpApi", "Properties": {"DefinitionUri": "definiton"}},
                "HttpApi": {"Type": "AWS::ApiGatewayV2::Api", "Properties": {"BodyS3Location": "definiton"}},
                "ServerlessStateMachine": {
                    "Type": "AWS::Serverless::StateMachine",
                    "Properties": {"DefinitionUri": "definiton"},
                },
                "StateMachine": {
                    "Type": "AWS::StepFunctions::StateMachine",
                    "Properties": {"DefinitionS3Location": "definiton"},
                },
            }
        }

        expected_resources = sorted(
            [
                "ServerlessFunction",
                "LambdaFunction",
                "ServerlessLayer",
                "LambdaLayer",
                "ServerlessApi",
                "RestApi",
                "ServerlessHttpApi",
                "HttpApi",
                "ServerlessStateMachine",
                "StateMachine",
            ]
        )

        local_path_mock.return_value = True
        infra_sync_executor = InfraSyncExecutor(self.build_context, self.package_context, self.deploy_context)

        processed_resources = infra_sync_executor._remove_unnecessary_fields(first_dict)

        self.assertEqual(processed_resources, expected_resources)

        expected_dict = {
            "Resources": {
                "ServerlessFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {},
                },
                "LambdaFunction": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {"Code": {}},
                },
                "ServerlessLayer": {
                    "Type": "AWS::Serverless::LayerVersion",
                    "Properties": {},
                },
                "LambdaLayer": {"Type": "AWS::Lambda::LayerVersion", "Properties": {}},
                "ServerlessApi": {"Type": "AWS::Serverless::Api", "Properties": {}},
                "RestApi": {"Type": "AWS::ApiGateway::RestApi", "Properties": {}},
                "ServerlessHttpApi": {
                    "Type": "AWS::Serverless::HttpApi",
                    "Properties": {},
                },
                "HttpApi": {"Type": "AWS::ApiGatewayV2::Api", "Properties": {}},
                "ServerlessStateMachine": {
                    "Type": "AWS::Serverless::StateMachine",
                    "Properties": {},
                },
                "StateMachine": {
                    "Type": "AWS::StepFunctions::StateMachine",
                    "Properties": {},
                },
            }
        }

        self.assertEqual(first_dict, expected_dict)

        second_dict = {
            "Resources": {
                "ServerlessFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {"CodeUri": "s3://location", "ImageUri": "s3://location"},
                },
                "LambdaFunction": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {
                        "Code": {
                            "ImageUri": "s3://location",
                            "S3Bucket": "s3://location",
                            "S3Key": "s3://location",
                            "S3ObjectVersion": "s3://location",
                        }
                    },
                },
                "ServerlessLayer": {
                    "Type": "AWS::Serverless::LayerVersion",
                    "Properties": {"ContentUri": "s3://location"},
                },
                "LambdaLayer": {"Type": "AWS::Lambda::LayerVersion", "Properties": {"Content": "s3://location"}},
                "ServerlessApi": {"Type": "AWS::Serverless::Api", "Properties": {"DefinitionBody": "s3://location"}},
                "RestApi": {"Type": "AWS::ApiGateway::RestApi", "Properties": {"BodyS3Location": "s3://location"}},
                "ServerlessHttpApi": {
                    "Type": "AWS::Serverless::HttpApi",
                    "Properties": {"DefinitionUri": "s3://location"},
                },
                "HttpApi": {"Type": "AWS::ApiGatewayV2::Api", "Properties": {"BodyS3Location": "s3://location"}},
                "ServerlessStateMachine": {
                    "Type": "AWS::Serverless::StateMachine",
                    "Properties": {"DefinitionUri": "s3://location"},
                },
                "StateMachine": {
                    "Type": "AWS::StepFunctions::StateMachine",
                    "Properties": {"DefinitionS3Location": "s3://location"},
                },
            }
        }

        processed_resources = infra_sync_executor._remove_unnecessary_fields(second_dict, expected_resources)
        self.assertEqual(processed_resources, expected_resources)

        self.assertEqual(second_dict, expected_dict)

    @patch("samcli.lib.sync.infra_sync_executor.is_local_path")
    @patch("samcli.lib.sync.infra_sync_executor.Session")
    def test_remove_metadata(self, session_mock, local_path_mock):
        self.template_dict = {
            "Resources": {
                "ServerlessFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {"CodeUri": "local/", "ImageUri": "image"},
                    "Metadata": {"SamResourceId": "Id"}
                }
            }
        }

        expected_dict = {
            "Resources": {
                "ServerlessFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {},
                }
            }
        }

        local_path_mock.return_value = True
        infra_sync_executor = InfraSyncExecutor(self.build_context, self.package_context, self.deploy_context)

        infra_sync_executor._remove_unnecessary_fields(self.template_dict)

        self.assertEqual(self.template_dict, expected_dict)
