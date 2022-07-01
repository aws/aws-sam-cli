from unittest import TestCase
from unittest.mock import patch, call, Mock
from botocore.exceptions import ClientError

from samcli.commands.list.resources.resources_context import ResourcesContext
from samcli.commands.local.cli_common.user_exceptions import InvalidSamTemplateException
from samcli.lib.translate.exceptions import InvalidSamDocumentException
from samcli.commands.exceptions import RegionError
from samcli.commands.list.exceptions import SamListError, SamListLocalResourcesNotFoundError, SamListUnknownClientError
from samtranslator.public.exceptions import InvalidDocumentException
from samcli.lib.translate.sam_template_validator import SamTemplateValidator


class TestResourcesContext(TestCase):
    @patch("samcli.commands.list.json_consumer.click.echo")
    @patch("samcli.commands.list.json_consumer.click.get_current_context")
    @patch("samcli.lib.list.resources.resource_mapping_producer._read_sam_file")
    @patch("samcli.lib.list.resources.resource_mapping_producer.ResourceMappingProducer.get_translated_dict")
    def test_resources_local_only_no_stack_name(
        self, mock_get_translated_dict, mock_sam_file_reader, patched_click_get_current_context, patched_click_echo
    ):
        mock_get_translated_dict.return_value = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Description": "sam-app-hello\nSample SAM Template for sam-app-hello\n",
            "Resources": {
                "HelloWorldFunction": {
                    "Properties": {
                        "Architectures": ["x86_64"],
                        "Code": {"S3Bucket": "bucket", "S3Key": "value"},
                        "Handler": "app.lambda_handler",
                        "Role": {"Fn::GetAtt": ["HelloWorldFunctionRole", "Arn"]},
                        "Runtime": "python3.8",
                        "Tags": [{"Key": "lambda:createdBy", "Value": "SAM"}],
                        "Timeout": 3,
                        "TracingConfig": {"Mode": "Active"},
                    },
                    "Type": "AWS::Lambda::Function",
                },
                "HelloWorldFunctionRole": {
                    "Properties": {
                        "AssumeRolePolicyDocument": {
                            "Statement": [
                                {
                                    "Action": ["sts:AssumeRole"],
                                    "Effect": "Allow",
                                    "Principal": {"Service": ["lambda.amazonaws.com"]},
                                }
                            ],
                            "Version": "2012-10-17",
                        },
                        "ManagedPolicyArns": [
                            "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
                            "arn:aws:iam::aws:policy/AWSXrayWriteOnlyAccess",
                        ],
                        "Tags": [{"Key": "lambda:createdBy", "Value": "SAM"}],
                    },
                    "Type": "AWS::IAM::Role",
                },
                "HelloWorldFunctionHelloWorldPermissionProd": {
                    "Properties": {
                        "Action": "lambda:InvokeFunction",
                        "FunctionName": {"Ref": "HelloWorldFunction"},
                        "Principal": "apigateway.amazonaws.com",
                        "SourceArn": {
                            "Fn::Sub": [
                                "arn:aws:execute-api:${AWS::Region}:${AWS::AccountId}:${__ApiId__}/${__Stage__}/GET/hello",
                                {"__ApiId__": {"Ref": "ServerlessRestApi"}, "__Stage__": "*"},
                            ]
                        },
                    },
                    "Type": "AWS::Lambda::Permission",
                },
                "ServerlessRestApi": {
                    "Properties": {
                        "Body": {
                            "info": {"version": "1.0", "title": {"Ref": "AWS::StackName"}},
                            "paths": {
                                "/hello": {
                                    "get": {
                                        "x-amazon-apigateway-integration": {
                                            "httpMethod": "POST",
                                            "type": "aws_proxy",
                                            "uri": {
                                                "Fn::Sub": "arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${HelloWorldFunction.Arn}/invocations"
                                            },
                                        },
                                        "responses": {},
                                    }
                                }
                            },
                            "swagger": "2.0",
                        }
                    },
                    "Type": "AWS::ApiGateway::RestApi",
                },
                "ServerlessRestApiDeploymentf5716dc08b": {
                    "Properties": {
                        "Description": "RestApi deployment id: f5716dc08b0d213bd0f2dfb686579c351b09ae49",
                        "RestApiId": {"Ref": "ServerlessRestApi"},
                        "StageName": "Stage",
                    },
                    "Type": "AWS::ApiGateway::Deployment",
                },
                "ServerlessRestApiProdStage": {
                    "Properties": {
                        "DeploymentId": {"Ref": "ServerlessRestApiDeploymentf5716dc08b"},
                        "RestApiId": {"Ref": "ServerlessRestApi"},
                        "StageName": "Prod",
                    },
                    "Type": "AWS::ApiGateway::Stage",
                },
            },
        }

        mock_sam_file_reader.return_value = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Transform": "AWS::Serverless-2016-10-31",
            "Description": "sam-app-hello\nSample SAM Template for sam-app-hello\n",
            "Globals": {"Function": {"Tracing": "Active", "Timeout": 3}},
            "Resources": {
                "HelloWorldFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "CodeUri": "hello_world/",
                        "Handler": "app.lambda_handler",
                        "Architectures": ["x86_64"],
                        "Runtime": "python3.8",
                        "Events": {"HelloWorld": {"Type": "Api", "Properties": {"Path": "/hello", "Method": "get"}}},
                    },
                }
            },
        }
        with ResourcesContext(
            stack_name=None, output="json", region="us-east-1", profile=None, template_file=None
        ) as resources_context:
            resources_context.run()
            expected_output = [
                call('{\n  "LogicalResourceId": "HelloWorldFunction",\n  "PhysicalResourceId": "-"\n}'),
                call('{\n  "LogicalResourceId": "HelloWorldFunctionRole",\n  "PhysicalResourceId": "-"\n}'),
                call(
                    '{\n  "LogicalResourceId": "HelloWorldFunctionHelloWorldPermissionProd",\n  "PhysicalResourceId": "-"\n}'
                ),
                call('{\n  "LogicalResourceId": "ServerlessRestApi",\n  "PhysicalResourceId": "-"\n}'),
                call(
                    '{\n  "LogicalResourceId": "ServerlessRestApiDeploymentf5716dc08b",\n  "PhysicalResourceId": "-"\n}'
                ),
                call('{\n  "LogicalResourceId": "ServerlessRestApiProdStage",\n  "PhysicalResourceId": "-"\n}'),
            ]
            self.assertEqual(expected_output, patched_click_echo.call_args_list)

    @patch("samcli.commands.list.json_consumer.click.echo")
    @patch("samcli.commands.list.json_consumer.click.get_current_context")
    @patch("samcli.lib.list.resources.resource_mapping_producer._read_sam_file")
    @patch("samcli.lib.list.resources.resource_mapping_producer.SamTemplateValidator.get_translated_template")
    def test_clienterror_exception(
        self, mock_get_translated_template, mock_sam_file_reader, patched_click_get_current_context, patched_click_echo
    ):
        mock_get_translated_template.side_effect = ClientError(
            {"Error": {"Code": "ExpiredToken", "Message": "The security token included in the request is expired"}},
            "DescribeStacks",
        )
        with self.assertRaises(SamListUnknownClientError):
            with ResourcesContext(
                stack_name=None, output="json", region="us-east-1", profile=None, template_file=None
            ) as resources_context:
                resources_context.run()

    @patch("samcli.commands.list.json_consumer.click.echo")
    @patch("samcli.commands.list.json_consumer.click.get_current_context")
    @patch("samcli.lib.list.resources.resource_mapping_producer._read_sam_file")
    @patch("samcli.lib.list.resources.resource_mapping_producer.SamTemplateValidator.get_translated_template")
    def test_get_translate_dict_invalid_template_error(
        self, mock_get_translated_template, mock_sam_file_reader, patched_click_get_current_context, patched_click_echo
    ):
        mock_sam_file_reader.return_value = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Transform": "AWS::Serverless-2016-10-31",
            "Description": "sam-app-hello\nSample SAM Template for sam-app-hello\n",
            "Globals": {"Function": {"Tracing": "Active", "Timeout": 3}},
            "Resources": {
                "HelloWorldFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "CodeUri": "hello_world/",
                        "Handler": "app.lambda_handler",
                        "Architectures": ["x86_64"],
                        "Runtime": "python3.8",
                        "Events": {"HelloWorld": {"Type": "Api", "Properties": {"Path": "/hello", "Method": "get"}}},
                    },
                }
            },
        }
        mock_get_translated_template.side_effect = InvalidSamDocumentException()
        with self.assertRaises(InvalidSamTemplateException):
            with ResourcesContext(
                stack_name=None, output="json", region="us-east-1", profile=None, template_file=None
            ) as resources_context:
                resources_context.run()
                self.assertEqual(patched_click_echo.call_args_list, "Template provided was invalid SAM Template.")

    @patch("samcli.commands.list.json_consumer.click.echo")
    @patch("samcli.commands.list.json_consumer.click.get_current_context")
    @patch("boto3.Session.region_name", None)
    def test_init_clients_no_region(self, patched_click_get_current_context, patched_click_echo):
        with self.assertRaises(RegionError):
            with ResourcesContext(
                stack_name="test", output="json", region=None, profile=None, template_file=None
            ) as resources_context:
                resources_context.init_clients()

    @patch("samcli.commands.list.json_consumer.click.echo")
    @patch("samcli.commands.list.json_consumer.click.get_current_context")
    @patch("boto3.Session.region_name", "us-east-1")
    def test_init_clients_no_input_region_get_region_from_session(
        self, patched_click_get_current_context, patched_click_echo
    ):
        with ResourcesContext(
            stack_name="test", output="json", region=None, profile=None, template_file=None
        ) as resources_context:
            resources_context.init_clients()
            self.assertEqual(resources_context.region, "us-east-1")

    @patch("samcli.lib.translate.sam_template_validator.Session")
    @patch("samcli.lib.translate.sam_template_validator.Translator")
    @patch("samcli.lib.translate.sam_template_validator.parser")
    def test_get_translated_template_raises_exception(self, sam_parser, sam_translator, boto_session_patch):
        managed_policy_mock = Mock()
        managed_policy_mock.load.return_value = {"policy": "SomePolicy"}
        template = {"a": "b"}

        parser = Mock()
        sam_parser.Parser.return_value = parser

        boto_session_mock = Mock()
        boto_session_patch.return_value = boto_session_mock

        translate_mock = Mock()
        translate_mock.translate.side_effect = InvalidDocumentException([Exception("message")])
        sam_translator.return_value = translate_mock

        validator = SamTemplateValidator(template, managed_policy_mock)

        with self.assertRaises(InvalidSamDocumentException):
            validator.get_translated_template()

        sam_translator.assert_called_once_with(
            managed_policy_map={"policy": "SomePolicy"}, sam_parser=parser, plugins=[], boto_session=boto_session_mock
        )

        boto_session_patch.assert_called_once_with(profile_name=None, region_name=None)
        translate_mock.translate.assert_called_once_with(sam_template=template, parameter_values={})
        sam_parser.Parser.assert_called_once()

    @patch("samcli.commands.list.json_consumer.click.echo")
    @patch("samcli.commands.list.json_consumer.click.get_current_context")
    @patch("samcli.lib.list.resources.resource_mapping_producer._read_sam_file")
    @patch("samcli.lib.list.resources.resource_mapping_producer.ResourceMappingProducer.get_translated_dict")
    @patch("samcli.lib.list.resources.resource_mapping_producer.SamLocalStackProvider.get_stacks")
    def test_resources_get_stacks_returns_empty(
        self,
        mock_get_stacks,
        mock_get_translated_dict,
        mock_sam_file_reader,
        patched_click_get_current_context,
        patched_click_echo,
    ):
        mock_get_translated_dict.return_value = {}
        mock_sam_file_reader.return_value = {}
        mock_get_stacks.return_value = ([], [])
        with self.assertRaises(SamListLocalResourcesNotFoundError):
            with ResourcesContext(
                stack_name=None, output="json", region="us-east-1", profile=None, template_file=None
            ) as resources_context:
                resources_context.run()
