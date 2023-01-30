from unittest import TestCase

from samtranslator.model.exceptions import ExceptionWithMessage
from unittest.mock import patch, call, Mock
from botocore.exceptions import ClientError, EndpointConnectionError, NoCredentialsError, BotoCoreError
from samtranslator.translator.arn_generator import NoRegionFound

from samcli.commands.list.resources.resources_context import ResourcesContext
from samcli.commands.local.cli_common.user_exceptions import InvalidSamTemplateException
from samcli.commands.validate.lib.exceptions import InvalidSamDocumentException
from samcli.commands.exceptions import RegionError, UserException
from samcli.commands.list.exceptions import (
    SamListLocalResourcesNotFoundError,
    SamListUnknownClientError,
    StackDoesNotExistInRegionError,
    SamListUnknownBotoCoreError,
)
from samtranslator.public.exceptions import InvalidDocumentException
from samcli.lib.translate.sam_template_validator import SamTemplateValidator
from samcli.lib.list.resources.resource_mapping_producer import ResourceMappingProducer
from samcli.lib.list.data_to_json_mapper import DataToJsonMapper
from samcli.commands.list.json_consumer import StringConsumerJsonOutput


TRANSLATED_DICT_RETURN = {
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

SAM_FILE_READER_RETURN = {
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


class TestResourcesContext(TestCase):
    @patch("samcli.commands.list.json_consumer.click.echo")
    @patch("samcli.commands.list.json_consumer.click.get_current_context")
    @patch("samcli.lib.list.resources.resource_mapping_producer.get_template_data")
    @patch("samcli.lib.list.resources.resource_mapping_producer.ResourceMappingProducer.get_translated_dict")
    def test_resources_context_run_local_only_no_stack_name(
        self, mock_get_translated_dict, mock_sam_file_reader, patched_click_get_current_context, patched_click_echo
    ):
        mock_get_translated_dict.return_value = TRANSLATED_DICT_RETURN

        mock_sam_file_reader.return_value = SAM_FILE_READER_RETURN
        with ResourcesContext(
            stack_name=None, output="json", region="us-east-1", profile=None, template_file=None
        ) as resources_context:
            resources_context.run()
            expected_output = [
                call(
                    '[\n  {\n    "LogicalResourceId": "HelloWorldFunction",\n    "PhysicalResourceId": "-"\n  },\n  {\n    "LogicalResourceId": "HelloWorldFunctionRole",\n    "PhysicalResourceId": "-"\n  },\n  {\n    "LogicalResourceId": "HelloWorldFunctionHelloWorldPermissionProd",\n    "PhysicalResourceId": "-"\n  },\n  {\n    "LogicalResourceId": "ServerlessRestApi",\n    "PhysicalResourceId": "-"\n  },\n  {\n    "LogicalResourceId": "ServerlessRestApiDeploymentf5716dc08b",\n    "PhysicalResourceId": "-"\n  },\n  {\n    "LogicalResourceId": "ServerlessRestApiProdStage",\n    "PhysicalResourceId": "-"\n  }\n]'
                )
            ]
            print(patched_click_echo.call_args_list)
            self.assertEqual(expected_output, patched_click_echo.call_args_list)


class TestResourceMappingProducerProduce(TestCase):
    @patch("samcli.commands.list.json_consumer.click.echo")
    @patch("samcli.commands.list.json_consumer.click.get_current_context")
    @patch("samcli.lib.list.resources.resource_mapping_producer.get_template_data")
    @patch("samcli.lib.list.resources.resource_mapping_producer.ResourceMappingProducer.get_translated_dict")
    def test_resources_local_only_no_stack_name(
        self, mock_get_translated_dict, mock_sam_file_reader, patched_click_get_current_context, patched_click_echo
    ):
        mock_get_translated_dict.return_value = TRANSLATED_DICT_RETURN

        mock_sam_file_reader.return_value = SAM_FILE_READER_RETURN
        resource_producer = ResourceMappingProducer(
            stack_name=None,
            region=None,
            profile=None,
            template_file=None,
            cloudformation_client=None,
            iam_client=None,
            mapper=DataToJsonMapper(),
            consumer=StringConsumerJsonOutput(),
        )
        resource_producer.produce()
        expected_output = [
            call(
                '[\n  {\n    "LogicalResourceId": "HelloWorldFunction",\n    "PhysicalResourceId": "-"\n  },\n  {\n    "LogicalResourceId": "HelloWorldFunctionRole",\n    "PhysicalResourceId": "-"\n  },\n  {\n    "LogicalResourceId": "HelloWorldFunctionHelloWorldPermissionProd",\n    "PhysicalResourceId": "-"\n  },\n  {\n    "LogicalResourceId": "ServerlessRestApi",\n    "PhysicalResourceId": "-"\n  },\n  {\n    "LogicalResourceId": "ServerlessRestApiDeploymentf5716dc08b",\n    "PhysicalResourceId": "-"\n  },\n  {\n    "LogicalResourceId": "ServerlessRestApiProdStage",\n    "PhysicalResourceId": "-"\n  }\n]'
            )
        ]
        self.assertEqual(expected_output, patched_click_echo.call_args_list)

    @patch("samcli.lib.translate.sam_template_validator.Session")
    @patch("samcli.lib.translate.sam_template_validator.Translator")
    @patch("samcli.lib.translate.sam_template_validator.parser")
    def test_get_translated_template_if_valid_raises_exception(self, sam_parser, sam_translator, boto_session_patch):
        managed_policy_mock = Mock()
        managed_policy_mock.load.return_value = {"policy": "SomePolicy"}
        template = {"a": "b"}

        parser = Mock()
        sam_parser.Parser.return_value = parser

        boto_session_mock = Mock()
        boto_session_patch.return_value = boto_session_mock

        translate_mock = Mock()
        translate_mock.translate.side_effect = InvalidDocumentException([ExceptionWithMessage("message")])
        sam_translator.return_value = translate_mock

        validator = SamTemplateValidator(template, managed_policy_mock)

        with self.assertRaises(InvalidSamDocumentException):
            validator.get_translated_template_if_valid()

        sam_translator.assert_called_once_with(
            managed_policy_map={"policy": "SomePolicy"}, sam_parser=parser, plugins=[], boto_session=boto_session_mock
        )

        boto_session_patch.assert_called_once_with(profile_name=None, region_name=None)
        translate_mock.translate.assert_called_once_with(sam_template=template, parameter_values={})
        sam_parser.Parser.assert_called_once()

    @patch("samcli.commands.list.json_consumer.click.echo")
    @patch("samcli.commands.list.json_consumer.click.get_current_context")
    @patch("samcli.lib.list.resources.resource_mapping_producer.get_template_data")
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
            resource_producer = ResourceMappingProducer(
                stack_name=None,
                region=None,
                profile=None,
                template_file=None,
                cloudformation_client=None,
                iam_client=None,
                mapper=DataToJsonMapper(),
                consumer=StringConsumerJsonOutput(),
            )
            resource_producer.produce()

    @patch("samcli.commands.list.json_consumer.click.echo")
    @patch("samcli.commands.list.json_consumer.click.get_current_context")
    @patch("samcli.lib.list.resources.resource_mapping_producer.get_template_data")
    @patch("samcli.lib.list.resources.resource_mapping_producer.ResourceMappingProducer.get_translated_dict")
    @patch("samcli.lib.list.resources.resource_mapping_producer.ResourceMappingProducer.get_resources_info")
    def test_resources_success_with_stack_name(
        self,
        mock_get_resources_info,
        mock_get_translated_dict,
        mock_sam_file_reader,
        patched_click_get_current_context,
        patched_click_echo,
    ):
        mock_get_resources_info.return_value = {
            "StackResources": [
                {"LogicalResourceId": "HelloWorldFunction", "PhysicalResourceId": "physical_resource_1"},
                {"LogicalResourceId": "HelloWorldFunctionRole", "PhysicalResourceId": "physical_resource_2"},
                {
                    "LogicalResourceId": "HelloWorldFunctionHelloWorldPermissionProd",
                    "PhysicalResourceId": "physical_resource_3",
                },
            ]
        }
        mock_get_translated_dict.return_value = TRANSLATED_DICT_RETURN

        mock_sam_file_reader.return_value = SAM_FILE_READER_RETURN
        resource_producer = ResourceMappingProducer(
            stack_name="test-stack",
            region="us-east-1",
            profile=None,
            template_file=None,
            cloudformation_client=None,
            iam_client=None,
            mapper=DataToJsonMapper(),
            consumer=StringConsumerJsonOutput(),
        )
        resource_producer.produce()
        expected_output = [
            call(
                '[\n  {\n    "LogicalResourceId": "HelloWorldFunction",\n    "PhysicalResourceId": "physical_resource_1"\n  },\n  {\n    "LogicalResourceId": "HelloWorldFunctionRole",\n    "PhysicalResourceId": "physical_resource_2"\n  },\n  {\n    "LogicalResourceId": "HelloWorldFunctionHelloWorldPermissionProd",\n    "PhysicalResourceId": "physical_resource_3"\n  },\n  {\n    "LogicalResourceId": "ServerlessRestApi",\n    "PhysicalResourceId": "-"\n  },\n  {\n    "LogicalResourceId": "ServerlessRestApiDeploymentf5716dc08b",\n    "PhysicalResourceId": "-"\n  },\n  {\n    "LogicalResourceId": "ServerlessRestApiProdStage",\n    "PhysicalResourceId": "-"\n  }\n]'
            )
        ]
        self.assertEqual(expected_output, patched_click_echo.call_args_list)


class TestGetTranslatedDict(TestCase):
    @patch("samcli.commands.list.json_consumer.click.echo")
    @patch("samcli.commands.list.json_consumer.click.get_current_context")
    @patch("samcli.lib.list.resources.resource_mapping_producer.get_template_data")
    @patch("samcli.lib.list.resources.resource_mapping_producer.SamTemplateValidator.get_translated_template_if_valid")
    def test_get_translate_dict_invalid_template_error(
        self,
        mock_get_translated_template_if_valid,
        mock_sam_file_reader,
        patched_click_get_current_context,
        patched_click_echo,
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
        mock_get_translated_template_if_valid.side_effect = InvalidSamDocumentException()
        with self.assertRaises(InvalidSamTemplateException):
            resource_producer = ResourceMappingProducer(
                stack_name=None,
                region="us-east-1",
                profile=None,
                template_file=None,
                cloudformation_client=None,
                iam_client=None,
                mapper=None,
                consumer=None,
            )
            resource_producer.get_translated_dict(mock_sam_file_reader.return_value)

    @patch("samcli.commands.list.json_consumer.click.echo")
    @patch("samcli.commands.list.json_consumer.click.get_current_context")
    @patch("samcli.lib.list.resources.resource_mapping_producer.get_template_data")
    @patch("samcli.lib.list.resources.resource_mapping_producer.SamTemplateValidator.get_translated_template_if_valid")
    def test_get_translated_dict_clienterror_exception(
        self,
        mock_get_translated_template_if_valid,
        mock_sam_file_reader,
        patched_click_get_current_context,
        patched_click_echo,
    ):
        mock_get_translated_template_if_valid.side_effect = ClientError(
            {"Error": {"Code": "ExpiredToken", "Message": "The security token included in the request is expired"}},
            "DescribeStacks",
        )
        with self.assertRaises(SamListUnknownClientError):
            resource_producer = ResourceMappingProducer(
                stack_name=None,
                region="us-east-1",
                profile=None,
                template_file=None,
                cloudformation_client=None,
                iam_client=None,
                mapper=None,
                consumer=None,
            )
            resource_producer.get_translated_dict(mock_sam_file_reader.return_value)

    @patch("samcli.commands.list.json_consumer.click.echo")
    @patch("samcli.commands.list.json_consumer.click.get_current_context")
    @patch("samcli.lib.list.resources.resource_mapping_producer.get_template_data")
    @patch("samcli.lib.list.resources.resource_mapping_producer.SamTemplateValidator.get_translated_template_if_valid")
    def test_get_translated_dict_no_credentials_exception(
        self,
        mock_get_translated_template_if_valid,
        mock_sam_file_reader,
        patched_click_get_current_context,
        patched_click_echo,
    ):
        mock_get_translated_template_if_valid.side_effect = NoCredentialsError()
        with self.assertRaises(UserException):
            resource_producer = ResourceMappingProducer(
                stack_name=None,
                region="us-east-1",
                profile=None,
                template_file=None,
                cloudformation_client=None,
                iam_client=None,
                mapper=None,
                consumer=None,
            )
            resource_producer.get_translated_dict(mock_sam_file_reader.return_value)

    @patch("samcli.commands.list.json_consumer.click.echo")
    @patch("samcli.commands.list.json_consumer.click.get_current_context")
    @patch("samcli.lib.list.resources.resource_mapping_producer.get_template_data")
    @patch("samcli.lib.list.resources.resource_mapping_producer.SamTemplateValidator.get_translated_template_if_valid")
    def test_get_translated_dict_no_region_found_exception(
        self,
        mock_get_translated_template_if_valid,
        mock_sam_file_reader,
        patched_click_get_current_context,
        patched_click_echo,
    ):
        mock_get_translated_template_if_valid.side_effect = NoRegionFound()
        with self.assertRaises(UserException):
            resource_producer = ResourceMappingProducer(
                stack_name=None,
                region=None,
                profile=None,
                template_file=None,
                cloudformation_client=None,
                iam_client=None,
                mapper=None,
                consumer=None,
            )
            resource_producer.get_translated_dict(mock_sam_file_reader.return_value)

    @patch("samcli.commands.list.json_consumer.click.echo")
    @patch("samcli.commands.list.json_consumer.click.get_current_context")
    @patch("samcli.lib.list.resources.resource_mapping_producer.SamTemplateValidator.get_translated_template_if_valid")
    @patch("samcli.lib.list.resources.resource_mapping_producer.yaml_parse")
    @patch("samcli.lib.list.resources.resource_mapping_producer.get_template_data")
    def test_get_translated_dict_calls_safe_yaml_parse(
        self,
        mock_sam_file_reader,
        mock_yaml_parse,
        mock_validate_template,
        patched_click_get_current_context,
        patched_click_echo,
    ):

        mock_sam_file_reader.return_value = SAM_FILE_READER_RETURN
        resource_producer = ResourceMappingProducer(
            stack_name=None,
            region=None,
            profile=None,
            template_file=None,
            cloudformation_client=None,
            iam_client=None,
            mapper=DataToJsonMapper(),
            consumer=StringConsumerJsonOutput(),
        )
        resource_producer.get_translated_dict(mock_sam_file_reader.return_value)

        mock_yaml_parse.assert_called_once()


class TestResourcesInitClients(TestCase):
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


class TestGetResourcesInfo(TestCase):
    @patch("samcli.commands.list.json_consumer.click.echo")
    @patch("samcli.commands.list.json_consumer.click.get_current_context")
    @patch("samcli.lib.list.resources.resource_mapping_producer.get_template_data")
    @patch("samcli.lib.list.resources.resource_mapping_producer.ResourceMappingProducer.get_translated_dict")
    @patch("samcli.commands.list.cli_common.list_common_context.get_boto_client_provider_with_config")
    def test_clienterror_stack_does_not_exist_in_region(
        self,
        mock_client_provider,
        mock_get_translated_dict,
        mock_sam_file_reader,
        patched_click_get_current_context,
        patched_click_echo,
    ):
        mock_client_provider.return_value.return_value.describe_stack_resources.side_effect = ClientError(
            {"Error": {"Code": "ValidationError", "Message": "Stack with id test does not exist"}}, "DescribeStacks"
        )
        mock_get_translated_dict.return_value = TRANSLATED_DICT_RETURN

        mock_sam_file_reader.return_value = SAM_FILE_READER_RETURN
        with self.assertRaises(StackDoesNotExistInRegionError):
            resource_producer = ResourceMappingProducer(
                stack_name="test-stack",
                region="us-east-1",
                profile=None,
                template_file=None,
                cloudformation_client=mock_client_provider.return_value.return_value,
                iam_client=None,
                mapper=None,
                consumer=None,
            )
            resource_producer.get_resources_info()

    @patch("samcli.commands.list.json_consumer.click.echo")
    @patch("samcli.commands.list.json_consumer.click.get_current_context")
    @patch("samcli.lib.list.resources.resource_mapping_producer.get_template_data")
    @patch("samcli.lib.list.resources.resource_mapping_producer.ResourceMappingProducer.get_translated_dict")
    @patch("samcli.commands.list.cli_common.list_common_context.get_boto_client_provider_with_config")
    def test_botocoreerror_invalid_region(
        self,
        mock_client_provider,
        mock_get_translated_dict,
        mock_sam_file_reader,
        patched_click_get_current_context,
        patched_click_echo,
    ):
        mock_client_provider.return_value.return_value.describe_stack_resources.side_effect = EndpointConnectionError(
            endpoint_url="https://cloudformation.test.amazonaws.com/"
        )
        mock_get_translated_dict.return_value = TRANSLATED_DICT_RETURN

        mock_sam_file_reader.return_value = SAM_FILE_READER_RETURN
        with self.assertRaises(SamListUnknownBotoCoreError):
            resource_producer = ResourceMappingProducer(
                stack_name="test-stack",
                region="us-east-1",
                profile=None,
                template_file=None,
                cloudformation_client=mock_client_provider.return_value.return_value,
                iam_client=None,
                mapper=None,
                consumer=None,
            )
            resource_producer.get_resources_info()

    @patch("samcli.commands.list.json_consumer.click.echo")
    @patch("samcli.commands.list.json_consumer.click.get_current_context")
    @patch("samcli.lib.list.resources.resource_mapping_producer.get_template_data")
    @patch("samcli.lib.list.resources.resource_mapping_producer.ResourceMappingProducer.get_translated_dict")
    @patch("samcli.commands.list.cli_common.list_common_context.get_boto_client_provider_with_config")
    def test_clienterror_token_error(
        self,
        mock_client_provider,
        mock_get_translated_dict,
        mock_sam_file_reader,
        patched_click_get_current_context,
        patched_click_echo,
    ):
        mock_client_provider.return_value.return_value.describe_stack_resources.side_effect = ClientError(
            {"Error": {"Code": "ExpiredToken", "Message": "The security token included in the request is expired"}},
            "DescribeStacks",
        )
        mock_get_translated_dict.return_value = TRANSLATED_DICT_RETURN

        mock_sam_file_reader.return_value = SAM_FILE_READER_RETURN
        with self.assertRaises(SamListUnknownClientError):
            resource_producer = ResourceMappingProducer(
                stack_name="test-stack",
                region="us-east-1",
                profile=None,
                template_file=None,
                cloudformation_client=mock_client_provider.return_value.return_value,
                iam_client=None,
                mapper=None,
                consumer=None,
            )
            resource_producer.get_resources_info()

    @patch("samcli.commands.list.json_consumer.click.echo")
    @patch("samcli.commands.list.json_consumer.click.get_current_context")
    @patch("samcli.lib.list.resources.resource_mapping_producer.get_template_data")
    @patch("samcli.lib.list.resources.resource_mapping_producer.ResourceMappingProducer.get_translated_dict")
    @patch("samcli.commands.list.cli_common.list_common_context.get_boto_client_provider_with_config")
    def test_stack_resource_not_in_response(
        self,
        mock_client_provider,
        mock_get_translated_dict,
        mock_sam_file_reader,
        patched_click_get_current_context,
        patched_click_echo,
    ):
        mock_client_provider.return_value.return_value.describe_stack_resources.return_value = {}
        mock_get_translated_dict.return_value = TRANSLATED_DICT_RETURN

        mock_sam_file_reader.return_value = SAM_FILE_READER_RETURN
        resource_producer = ResourceMappingProducer(
            stack_name="test-stack",
            region="us-east-1",
            profile=None,
            template_file=None,
            cloudformation_client=mock_client_provider.return_value.return_value,
            iam_client=None,
            mapper=None,
            consumer=None,
        )
        response = resource_producer.get_resources_info()
        self.assertEqual(response, {"StackResources": []})

    @patch("samcli.commands.list.json_consumer.click.echo")
    @patch("samcli.commands.list.json_consumer.click.get_current_context")
    @patch("samcli.lib.list.resources.resource_mapping_producer.get_template_data")
    @patch("samcli.lib.list.resources.resource_mapping_producer.ResourceMappingProducer.get_translated_dict")
    @patch("samcli.commands.list.cli_common.list_common_context.get_boto_client_provider_with_config")
    def test_stack_resource_in_response(
        self,
        mock_client_provider,
        mock_get_translated_dict,
        mock_sam_file_reader,
        patched_click_get_current_context,
        patched_click_echo,
    ):
        mock_client_provider.return_value.return_value.describe_stack_resources.return_value = {
            "StackResources": [{"StackName": "sam-app-hello"}]
        }
        mock_get_translated_dict.return_value = TRANSLATED_DICT_RETURN

        mock_sam_file_reader.return_value = SAM_FILE_READER_RETURN
        resource_producer = ResourceMappingProducer(
            stack_name="test-stack",
            region="us-east-1",
            profile=None,
            template_file=None,
            cloudformation_client=mock_client_provider.return_value.return_value,
            iam_client=None,
            mapper=None,
            consumer=None,
        )
        response = resource_producer.get_resources_info()
        self.assertEqual(response, {"StackResources": [{"StackName": "sam-app-hello"}]})
