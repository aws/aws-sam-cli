from unittest import TestCase
from unittest.mock import patch, call, Mock
from botocore.exceptions import ClientError, EndpointConnectionError, NoCredentialsError, BotoCoreError

from samcli.commands.list.endpoints.endpoints_context import EndpointsContext
from samcli.commands.list.exceptions import (
    SamListLocalResourcesNotFoundError,
    SamListUnknownClientError,
    SamListUnknownBotoCoreError,
)
from samcli.lib.providers.sam_stack_provider import SamLocalStackProvider
from samcli.lib.list.endpoints.endpoints_producer import EndpointsProducer, APIGatewayEnum
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

TRANSLATED_DICT_RETURN_WITH_APIS = {
    "AWSTemplateFormatVersion": "2010-09-09",
    "Description": "sam-app-hello\nSample SAM Template for sam-app-hello\n",
    "Resources": {
        "customDomainCert": {
            "Type": "AWS::CertificateManager::Certificate",
            "Properties": {"DomainName": "api7.zhandr.people.aws.dev", "ValidationMethod": "DNS"},
        },
        "BPMapping1": {
            "Type": "AWS::ApiGateway::BasePathMapping",
            "Properties": {"DomainName": "apigw_dm_mapping_LID", "RestApiId": "test_apigw_restapi", "Stage": "String"},
        },
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
        "HelloWorldFunctionUrl": {
            "Properties": {"AuthType": "AWS_IAM", "TargetFunctionArn": {"Ref": "HelloWorldFunction"}},
            "Type": "AWS::Lambda::Url",
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
        "HelloWorldFunctionHelloWorld2PermissionProd": {
            "Properties": {
                "Action": "lambda:InvokeFunction",
                "FunctionName": {"Ref": "HelloWorldFunction"},
                "Principal": "apigateway.amazonaws.com",
                "SourceArn": {
                    "Fn::Sub": [
                        "arn:aws:execute-api:${AWS::Region}:${AWS::AccountId}:${__ApiId__}/${__Stage__}/GET, PUT/hello2",
                        {"__ApiId__": {"Ref": "ServerlessRestApi"}, "__Stage__": "*"},
                    ]
                },
            },
            "Type": "AWS::Lambda::Permission",
        },
        "TestResource2": {
            "Properties": {
                "Body": {
                    "info": {"version": "1.0", "description": "Test resources", "title": {"Ref": "AWS::StackName"}},
                    "paths": {},
                    "openapi": "3.0.1",
                    "tags": [{"name": "httpapi:createdBy", "x-amazon-apigateway-tag-value": "SAM"}],
                }
            },
            "Type": "AWS::ApiGatewayV2::Api",
        },
        "TestResource5": {
            "Properties": {
                "Body": {
                    "info": {"version": "1.0", "description": "Test resources", "title": {"Ref": "AWS::StackName"}},
                    "paths": {},
                    "openapi": "3.0.1",
                    "tags": [{"name": "httpapi:createdBy", "x-amazon-apigateway-tag-value": "SAM"}],
                }
            },
            "Type": "AWS::ApiGatewayV2::Api",
        },
        "ApiGatewayDomainNameV28437445d28": {
            "Properties": {
                "DomainName": "api7.zhandr.people.aws.dev",
                "DomainNameConfigurations": [
                    {"CertificateArn": {"Ref": "customDomainCert"}, "EndpointType": "REGIONAL"}
                ],
                "Tags": {"httpapi:createdBy": "SAM"},
            },
            "Type": "AWS::ApiGatewayV2::DomainName",
        },
        "TestResource2ApiMapping": {
            "Properties": {
                "ApiId": {"Ref": "TestResource2"},
                "DomainName": {"Ref": "ApiGatewayDomainNameV28437445d28"},
                "Stage": {"Ref": "TestResource2Test2Stage"},
            },
            "Type": "AWS::ApiGatewayV2::ApiMapping",
        },
        "TestResource2Test2Stage": {
            "Properties": {
                "ApiId": {"Ref": "TestResource2"},
                "AutoDeploy": True,
                "StageName": "Test2",
                "Tags": {"httpapi:createdBy": "SAM"},
            },
            "Type": "AWS::ApiGatewayV2::Stage",
        },
        "TestResource4": {
            "Properties": {
                "Body": {
                    "info": {"version": "1.0", "description": "Test resources", "title": {"Ref": "AWS::StackName"}},
                    "paths": {},
                    "openapi": "3.0.1",
                    "tags": [{"name": "httpapi:createdBy", "x-amazon-apigateway-tag-value": "SAM"}],
                }
            },
            "Type": "AWS::ApiGatewayV2::Api",
        },
        "TestResource4Test2Stage": {
            "Properties": {
                "ApiId": {"Ref": "TestResource4"},
                "AutoDeploy": True,
                "StageName": "Test2",
                "Tags": {"httpapi:createdBy": "SAM"},
            },
            "Type": "AWS::ApiGatewayV2::Stage",
        },
        "ServerlessRestApi": {
            "Properties": {
                "Body": {
                    "info": {"version": "1.0", "title": {"Ref": "AWS::StackName"}},
                    "paths": {
                        "/hello2": {
                            "get, put": {
                                "x-amazon-apigateway-integration": {
                                    "httpMethod": "POST",
                                    "type": "aws_proxy",
                                    "uri": {
                                        "Fn::Sub": "arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${HelloWorldFunction.Arn}/invocations"
                                    },
                                },
                                "responses": {},
                            }
                        },
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
                        },
                    },
                    "swagger": "2.0",
                }
            },
            "Type": "AWS::ApiGateway::RestApi",
        },
        "ServerlessRestApiDeployment88d73b1fc4": {
            "Properties": {
                "Description": "RestApi deployment id: 88d73b1fc436b53afc5f54ce63096d44e97b741b",
                "RestApiId": {"Ref": "ServerlessRestApi"},
                "StageName": "Stage",
            },
            "Type": "AWS::ApiGateway::Deployment",
        },
        "ServerlessRestApiProdStage": {
            "Properties": {
                "DeploymentId": {"Ref": "ServerlessRestApiDeployment88d73b1fc4"},
                "RestApiId": {"Ref": "ServerlessRestApi"},
                "StageName": "Prod",
            },
            "Type": "AWS::ApiGateway::Stage",
        },
    },
}

SAM_APP_HELLO_RETURN_RESPONSE = {
    "StackResources": [
        {
            "StackName": "sam-app-hello6",
            "LogicalResourceId": "ApiGatewayDomainName1",
            "PhysicalResourceId": "test.custom.domain1",
            "ResourceType": "AWS::ApiGatewayV2::DomainName",
            "ResourceStatus": "CREATE_COMPLETE",
            "DriftInformation": {"StackResourceDriftStatus": "NOT_CHECKED"},
        },
        {
            "StackName": "sam-app-hello6",
            "LogicalResourceId": "HelloWorldFunction",
            "PhysicalResourceId": "sam-app-hello6-HelloWorldFunction-testID",
            "ResourceType": "AWS::Lambda::Function",
            "ResourceStatus": "CREATE_COMPLETE",
            "DriftInformation": {"StackResourceDriftStatus": "NOT_CHECKED"},
        },
        {
            "StackName": "sam-app-hello6",
            "LogicalResourceId": "HelloWorldFunctionUrl",
            "PhysicalResourceId": "arn:aws:lambda:us-east-1:function:sam-app-hello6-HelloWorldFunction-testID",
            "ResourceType": "AWS::Lambda::Url",
            "ResourceStatus": "CREATE_COMPLETE",
            "DriftInformation": {"StackResourceDriftStatus": "NOT_CHECKED"},
        },
        {
            "StackName": "sam-app-hello6",
            "LogicalResourceId": "ServerlessRestApi",
            "PhysicalResourceId": "jwompba769",
            "ResourceType": "AWS::ApiGateway::RestApi",
            "ResourceStatus": "CREATE_COMPLETE",
            "DriftInformation": {"StackResourceDriftStatus": "NOT_CHECKED"},
        },
        {
            "StackName": "sam-app-hello6",
            "LogicalResourceId": "ServerlessRestApiDeployment78c5316093",
            "PhysicalResourceId": "lulx9h",
            "ResourceType": "AWS::ApiGateway::Deployment",
            "ResourceStatus": "CREATE_COMPLETE",
            "DriftInformation": {"StackResourceDriftStatus": "NOT_CHECKED"},
        },
        {
            "StackName": "sam-app-hello6",
            "LogicalResourceId": "ServerlessRestApiProdStage",
            "PhysicalResourceId": "Prod",
            "ResourceType": "AWS::ApiGateway::Stage",
            "ResourceStatus": "CREATE_COMPLETE",
            "DriftInformation": {"StackResourceDriftStatus": "NOT_CHECKED"},
        },
        {
            "StackName": "sam-app-hello6",
            "LogicalResourceId": "TestResource2",
            "PhysicalResourceId": "erj31jdyw5",
            "ResourceType": "AWS::ApiGatewayV2::Api",
            "ResourceStatus": "CREATE_COMPLETE",
            "DriftInformation": {"StackResourceDriftStatus": "NOT_CHECKED"},
        },
        {
            "StackName": "sam-app-hello6",
            "LogicalResourceId": "TestResource2ApiMapping",
            "PhysicalResourceId": "rut5pp",
            "ResourceType": "AWS::ApiGatewayV2::ApiMapping",
            "ResourceStatus": "CREATE_COMPLETE",
            "DriftInformation": {"StackResourceDriftStatus": "NOT_CHECKED"},
        },
        {
            "StackName": "sam-app-hello6",
            "LogicalResourceId": "TestResource2Test2Stage",
            "PhysicalResourceId": "Test2",
            "ResourceType": "AWS::ApiGatewayV2::Stage",
            "ResourceStatus": "CREATE_COMPLETE",
            "DriftInformation": {"StackResourceDriftStatus": "NOT_CHECKED"},
        },
        {
            "StackName": "sam-app-hello6",
            "LogicalResourceId": "TestResource4",
            "PhysicalResourceId": "5u9ekr1d32",
            "ResourceType": "AWS::ApiGatewayV2::Api",
            "ResourceStatus": "CREATE_COMPLETE",
            "DriftInformation": {"StackResourceDriftStatus": "NOT_CHECKED"},
        },
        {
            "StackName": "sam-app-hello6",
            "LogicalResourceId": "TestResource4Test2Stage",
            "PhysicalResourceId": "Test2",
            "ResourceType": "AWS::ApiGatewayV2::Stage",
            "ResourceStatus": "CREATE_COMPLETE",
            "DriftInformation": {"StackResourceDriftStatus": "NOT_CHECKED"},
        },
        {
            "StackName": "sam-app-hello6",
            "LogicalResourceId": "customDomainCert",
            "PhysicalResourceId": "arn:aws:acm:us-east-1:certificate",
            "ResourceType": "AWS::CertificateManager::Certificate",
            "ResourceStatus": "CREATE_COMPLETE",
            "DriftInformation": {"StackResourceDriftStatus": "NOT_CHECKED"},
        },
        {
            "StackName": "sam-app-hello6",
            "LogicalResourceId": "test_apigw_restapi",
            "PhysicalResourceId": "testPID",
            "ResourceType": "AWS::ApiGateway::RestApi",
            "ResourceStatus": "CREATE_COMPLETE",
            "DriftInformation": {"StackResourceDriftStatus": "NOT_CHECKED"},
        },
        {
            "StackName": "sam-app-hello6",
            "LogicalResourceId": "apigw_dm_mapping_LID",
            "PhysicalResourceId": "test.custom.bpmapping.domain",
            "ResourceType": "AWS::ApiGateway::DomainName",
        },
        {
            "StackName": "sam-app-hello6",
            "LogicalResourceId": "BPMapping1",
            "PhysicalResourceId": "bp_mapping_PID",
            "ResourceType": "AWS::ApiGateway::BasePathMapping",
        },
    ],
    "ResponseMetadata": {
        "RequestId": "b15914d5-009b-46ce-aab8-458efc09f34d",
        "HTTPStatusCode": 200,
        "HTTPHeaders": {
            "x-amzn-requestid": "b15914d5-009b-46ce-aab8-458efc09f34d",
            "content-type": "text/xml",
            "content-length": "10370",
            "date": "Mon, 25 Jul 2022 20:27:05 GMT",
        },
        "RetryAttempts": 0,
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


class TestEndpointsInitClients(TestCase):
    @patch("samcli.commands.list.json_consumer.click.echo")
    @patch("samcli.commands.list.json_consumer.click.get_current_context")
    @patch("boto3.Session.region_name", "us-east-1")
    def test_init_clients_no_input_region_get_region_from_session(
        self, patched_click_get_current_context, patched_click_echo
    ):
        with EndpointsContext(
            stack_name="test", output="json", region=None, profile=None, template_file=None
        ) as endpoints_context:
            endpoints_context.init_clients()
            self.assertEqual(endpoints_context.region, "us-east-1")


class TestGetFunctionUrl(TestCase):
    @patch("samcli.commands.list.json_consumer.click.echo")
    @patch("samcli.commands.list.json_consumer.click.get_current_context")
    @patch("samcli.commands.list.cli_common.list_common_context.get_boto_client_provider_with_config")
    def test_clienterror_resource_not_found(
        self,
        mock_client_provider,
        patched_click_get_current_context,
        patched_click_echo,
    ):
        mock_client_provider.return_value.return_value.get_resource.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "The resource you requested does not exist"}},
            "GetResources",
        )
        endpoint_producer = EndpointsProducer(
            stack_name=None,
            region="us-east-1",
            profile=None,
            template_file=None,
            cloudformation_client=None,
            iam_client=None,
            cloudcontrol_client=mock_client_provider.return_value.return_value,
            apigateway_client=None,
            apigatewayv2_client=None,
            mapper=None,
            consumer=None,
        )
        response = endpoint_producer.get_function_url("testID")
        self.assertEqual(response, "-")

    @patch("samcli.commands.list.json_consumer.click.echo")
    @patch("samcli.commands.list.json_consumer.click.get_current_context")
    @patch("samcli.commands.list.cli_common.list_common_context.get_boto_client_provider_with_config")
    def test_clienterror_others(
        self,
        mock_client_provider,
        patched_click_get_current_context,
        patched_click_echo,
    ):
        mock_client_provider.return_value.return_value.get_resource.side_effect = ClientError(
            {"Error": {"Code": "ExpiredToken", "Message": "The security token included in the request is expired"}},
            "DescribeStacks",
        )
        with self.assertRaises(SamListUnknownClientError):
            endpoint_producer = EndpointsProducer(
                stack_name=None,
                region="us-east-1",
                profile=None,
                template_file=None,
                cloudformation_client=None,
                iam_client=None,
                cloudcontrol_client=mock_client_provider.return_value.return_value,
                apigateway_client=None,
                apigatewayv2_client=None,
                mapper=None,
                consumer=None,
            )
            endpoint_producer.get_function_url("testID")

    @patch("samcli.commands.list.json_consumer.click.echo")
    @patch("samcli.commands.list.json_consumer.click.get_current_context")
    @patch("samcli.commands.list.cli_common.list_common_context.get_boto_client_provider_with_config")
    def test_properties_not_in_response(
        self,
        mock_client_provider,
        patched_click_get_current_context,
        patched_click_echo,
    ):
        mock_client_provider.return_value.return_value.get_resource.return_value = {}
        endpoint_producer = EndpointsProducer(
            stack_name=None,
            region="us-east-1",
            profile=None,
            template_file=None,
            cloudformation_client=None,
            iam_client=None,
            cloudcontrol_client=mock_client_provider.return_value.return_value,
            apigateway_client=None,
            apigatewayv2_client=None,
            mapper=None,
            consumer=None,
        )
        response = endpoint_producer.get_function_url("testID")
        self.assertEqual(response, "-")

    @patch("samcli.commands.list.json_consumer.click.echo")
    @patch("samcli.commands.list.json_consumer.click.get_current_context")
    @patch("samcli.commands.list.cli_common.list_common_context.get_boto_client_provider_with_config")
    def test_properties_in_response(
        self,
        mock_client_provider,
        patched_click_get_current_context,
        patched_click_echo,
    ):
        mock_client_provider.return_value.return_value.get_resource.return_value = {
            "TypeName": "AWS::Lambda::Url",
            "ResourceDescription": {
                "Identifier": "testid",
                "Properties": '{"FunctionArn":"arn:aws:lambda:sam-app-hello-HelloWorldFunction","FunctionUrl":"https://test.lambda-url.us-east-1.on.aws/","AuthType":"AWS_IAM"}',
            },
            "ResponseMetadata": {
                "RequestId": "testID",
                "HTTPStatusCode": 200,
                "HTTPHeaders": {
                    "x-amzn-requestid": "testID",
                    "date": "testDate",
                    "content-type": "application/x-amz-json-1.0",
                    "content-length": "408",
                },
                "RetryAttempts": 0,
            },
        }
        endpoint_producer = EndpointsProducer(
            stack_name=None,
            region="us-east-1",
            profile=None,
            template_file=None,
            cloudformation_client=None,
            iam_client=None,
            cloudcontrol_client=mock_client_provider.return_value.return_value,
            apigateway_client=None,
            apigatewayv2_client=None,
            mapper=None,
            consumer=None,
        )
        response = endpoint_producer.get_function_url("testID")
        self.assertEqual(response, "https://test.lambda-url.us-east-1.on.aws/")


class TestGetStages(TestCase):
    @patch("samcli.commands.list.json_consumer.click.echo")
    @patch("samcli.commands.list.json_consumer.click.get_current_context")
    @patch("samcli.commands.list.cli_common.list_common_context.get_boto_client_provider_with_config")
    def test_apigw_v2_stages(
        self,
        mock_client_provider,
        patched_click_get_current_context,
        patched_click_echo,
    ):
        mock_client_provider.return_value.return_value.get_stages.return_value = {
            "ResponseMetadata": {
                "RequestId": "testid",
                "HTTPStatusCode": 200,
                "HTTPHeaders": {
                    "date": "Mon, 18 Jul 2022 20:59:15 GMT",
                    "content-type": "application/json",
                    "content-length": "762",
                    "connection": "keep-alive",
                    "x-amzn-requestid": "testid",
                    "access-control-allow-origin": "*",
                    "x-amz-apigw-id": "testid",
                    "access-control-expose-headers": "x-amzn-RequestId,x-amzn-ErrorType,x-amzn-ErrorMessage,Date",
                    "x-amzn-trace-id": "Root=testid",
                },
                "RetryAttempts": 0,
            },
            "Items": [
                {
                    "AutoDeploy": True,
                    "DefaultRouteSettings": {"DetailedMetricsEnabled": False},
                    "RouteSettings": {},
                    "StageName": "$default",
                    "StageVariables": {},
                }
            ],
        }
        endpoint_producer = EndpointsProducer(
            stack_name=None,
            region="us-east-1",
            profile=None,
            template_file=None,
            cloudformation_client=None,
            iam_client=None,
            cloudcontrol_client=None,
            apigateway_client=None,
            apigatewayv2_client=mock_client_provider.return_value.return_value,
            mapper=None,
            consumer=None,
        )
        response = endpoint_producer.get_stage_list("testID", APIGatewayEnum.API_GATEWAY_V2)
        self.assertEqual(response, ["$default"])

    @patch("samcli.commands.list.json_consumer.click.echo")
    @patch("samcli.commands.list.json_consumer.click.get_current_context")
    @patch("samcli.commands.list.cli_common.list_common_context.get_boto_client_provider_with_config")
    def test_apigw_stages(
        self,
        mock_client_provider,
        patched_click_get_current_context,
        patched_click_echo,
    ):
        mock_client_provider.return_value.return_value.get_stages.return_value = {
            "ResponseMetadata": {
                "RequestId": "testID",
                "HTTPStatusCode": 200,
                "HTTPHeaders": {
                    "date": "Mon, 18 Jul 2022 21:15:06 GMT",
                    "content-type": "application/json",
                    "content-length": "679",
                    "connection": "keep-alive",
                    "x-amzn-requestid": "testID",
                    "x-amz-apigw-id": "testID",
                },
                "RetryAttempts": 0,
            },
            "item": [
                {
                    "deploymentId": "t50nmu",
                    "stageName": "Prod",
                    "cacheClusterEnabled": False,
                    "cacheClusterStatus": "NOT_AVAILABLE",
                    "methodSettings": {},
                    "tracingEnabled": False,
                    "tags": {"aws:cloudformation:logical-id": "testID", "aws:cloudformation:stack-name": "testStack"},
                },
                {
                    "deploymentId": "t50nmu",
                    "stageName": "Stage",
                    "cacheClusterEnabled": False,
                    "cacheClusterStatus": "NOT_AVAILABLE",
                    "methodSettings": {},
                    "tracingEnabled": False,
                },
            ],
        }
        endpoint_producer = EndpointsProducer(
            stack_name=None,
            region="us-east-1",
            profile=None,
            template_file=None,
            cloudformation_client=None,
            iam_client=None,
            cloudcontrol_client=None,
            apigateway_client=mock_client_provider.return_value.return_value,
            apigatewayv2_client=None,
            mapper=None,
            consumer=None,
        )
        response = endpoint_producer.get_stage_list("testID", APIGatewayEnum.API_GATEWAY)
        self.assertEqual(response, ["Prod", "Stage"])

    @patch("samcli.commands.list.json_consumer.click.echo")
    @patch("samcli.commands.list.json_consumer.click.get_current_context")
    @patch("samcli.commands.list.cli_common.list_common_context.get_boto_client_provider_with_config")
    def test_apigw_stages_empty_return(
        self,
        mock_client_provider,
        patched_click_get_current_context,
        patched_click_echo,
    ):
        mock_client_provider.return_value.return_value.get_stages.return_value = {
            "ResponseMetadata": {
                "RequestId": "testID",
                "HTTPStatusCode": 200,
                "HTTPHeaders": {
                    "date": "Mon, 18 Jul 2022 21:15:06 GMT",
                    "content-type": "application/json",
                    "content-length": "679",
                    "connection": "keep-alive",
                    "x-amzn-requestid": "testID",
                    "x-amz-apigw-id": "testID",
                },
                "RetryAttempts": 0,
            },
        }
        endpoint_producer = EndpointsProducer(
            stack_name=None,
            region="us-east-1",
            profile=None,
            template_file=None,
            cloudformation_client=None,
            iam_client=None,
            cloudcontrol_client=None,
            apigateway_client=mock_client_provider.return_value.return_value,
            apigatewayv2_client=None,
            mapper=None,
            consumer=None,
        )
        response = endpoint_producer.get_stage_list("testID", APIGatewayEnum.API_GATEWAY)
        self.assertEqual(response, [])

    @patch("samcli.commands.list.json_consumer.click.echo")
    @patch("samcli.commands.list.json_consumer.click.get_current_context")
    @patch("samcli.commands.list.cli_common.list_common_context.get_boto_client_provider_with_config")
    def test_get_stage_list_unknown_clienterror(
        self,
        mock_client_provider,
        patched_click_get_current_context,
        patched_click_echo,
    ):
        mock_client_provider.return_value.return_value.get_stages.side_effect = ClientError(
            {"Error": {"Code": "ExpiredToken", "Message": "The security token included in the request is expired"}},
            "DescribeStacks",
        )
        with self.assertRaises(SamListUnknownClientError):
            endpoint_producer = EndpointsProducer(
                stack_name=None,
                region="us-east-1",
                profile=None,
                template_file=None,
                cloudformation_client=None,
                iam_client=None,
                cloudcontrol_client=None,
                apigateway_client=mock_client_provider.return_value.return_value,
                apigatewayv2_client=mock_client_provider.return_value.return_value,
                mapper=None,
                consumer=None,
            )
            endpoint_producer.get_stage_list("testID", APIGatewayEnum.API_GATEWAY)

    @patch("samcli.commands.list.json_consumer.click.echo")
    @patch("samcli.commands.list.json_consumer.click.get_current_context")
    @patch("samcli.commands.list.cli_common.list_common_context.get_boto_client_provider_with_config")
    def test_get_stage_list_not_found_exception_clienterror(
        self,
        mock_client_provider,
        patched_click_get_current_context,
        patched_click_echo,
    ):
        mock_client_provider.return_value.return_value.get_stages.side_effect = ClientError(
            {"Error": {"Code": "NotFoundException", "Message": ""}},
            "DescribeStacks",
        )
        endpoint_producer = EndpointsProducer(
            stack_name=None,
            region="us-east-1",
            profile=None,
            template_file=None,
            cloudformation_client=None,
            iam_client=None,
            cloudcontrol_client=None,
            apigateway_client=mock_client_provider.return_value.return_value,
            apigatewayv2_client=mock_client_provider.return_value.return_value,
            mapper=None,
            consumer=None,
        )
        response = endpoint_producer.get_stage_list("testID", APIGatewayEnum.API_GATEWAY)
        self.assertEqual(response, [])

    @patch("samcli.commands.list.json_consumer.click.echo")
    @patch("samcli.commands.list.json_consumer.click.get_current_context")
    @patch("samcli.commands.list.cli_common.list_common_context.get_boto_client_provider_with_config")
    def test_get_stage_list_unknown_botocore_error(
        self,
        mock_client_provider,
        patched_click_get_current_context,
        patched_click_echo,
    ):
        mock_client_provider.return_value.return_value.get_stages.side_effect = EndpointConnectionError(
            endpoint_url="https://cloudformation.test.amazonaws.com/"
        )
        with self.assertRaises(SamListUnknownBotoCoreError):
            endpoint_producer = EndpointsProducer(
                stack_name=None,
                region="us-east-1",
                profile=None,
                template_file=None,
                cloudformation_client=None,
                iam_client=None,
                cloudcontrol_client=None,
                apigateway_client=mock_client_provider.return_value.return_value,
                apigatewayv2_client=mock_client_provider.return_value.return_value,
                mapper=None,
                consumer=None,
            )
            endpoint_producer.get_stage_list("testID", APIGatewayEnum.API_GATEWAY)


class TestBuildAPIGWEndpoints(TestCase):
    @patch("samcli.commands.list.json_consumer.click.echo")
    @patch("samcli.commands.list.json_consumer.click.get_current_context")
    def test_build_api_gw_endpoints(
        self,
        patched_click_get_current_context,
        patched_click_echo,
    ):
        endpoint_producer = EndpointsProducer(
            stack_name=None,
            region="us-east-1",
            profile=None,
            template_file=None,
            cloudformation_client=None,
            iam_client=None,
            cloudcontrol_client=None,
            apigateway_client=None,
            apigatewayv2_client=None,
            mapper=None,
            consumer=None,
        )
        repsonse1 = endpoint_producer.build_api_gw_endpoints("testID", [])
        self.assertEqual(repsonse1, [])
        repsonse2 = endpoint_producer.build_api_gw_endpoints("testID", ["Prod"])
        self.assertEqual(repsonse2, ["https://testID.execute-api.us-east-1.amazonaws.com/Prod"])


class TestEndpointsProducerProduce(TestCase):
    @patch("samcli.commands.list.json_consumer.click.echo")
    @patch("samcli.commands.list.json_consumer.click.get_current_context")
    @patch("samcli.lib.list.endpoints.endpoints_producer.SamLocalStackProvider.get_stacks")
    @patch("samcli.lib.list.endpoints.endpoints_producer.get_template_data")
    @patch("samcli.lib.list.endpoints.endpoints_producer.EndpointsProducer.get_translated_dict")
    def test_produce_resources_not_found_error(
        self,
        mock_get_translated_dict,
        mock_get_template_data,
        mock_get_stacks,
        patched_click_get_current_context,
        patched_click_echo,
    ):
        mock_get_template_data.return_value = {}
        mock_get_translated_dict.return_value = {}
        mock_get_stacks.return_value = ([], [])
        endpoint_producer = EndpointsProducer(
            stack_name=None,
            region="us-east-1",
            profile=None,
            template_file=None,
            cloudformation_client=None,
            iam_client=None,
            cloudcontrol_client=None,
            apigateway_client=None,
            apigatewayv2_client=None,
            mapper=None,
            consumer=None,
        )
        with self.assertRaises(SamListLocalResourcesNotFoundError):
            endpoint_producer.produce()

    @patch("samcli.commands.list.json_consumer.click.echo")
    @patch("samcli.commands.list.json_consumer.click.get_current_context")
    @patch("samcli.lib.list.endpoints.endpoints_producer.get_template_data")
    @patch("samcli.lib.list.endpoints.endpoints_producer.EndpointsProducer.get_translated_dict")
    def test_produce_no_stack_name_json(
        self,
        mock_get_translated_dict,
        mock_get_template_data,
        patched_click_get_current_context,
        patched_click_echo,
    ):
        mock_get_template_data.return_value = {}
        mock_get_translated_dict.return_value = TRANSLATED_DICT_RETURN_WITH_APIS

        stacks = SamLocalStackProvider.get_stacks(
            template_file="", template_dictionary=mock_get_translated_dict.return_value
        )
        endpoint_producer = EndpointsProducer(
            stack_name=None,
            region="us-east-1",
            profile=None,
            template_file=None,
            cloudformation_client=None,
            iam_client=None,
            cloudcontrol_client=None,
            apigateway_client=None,
            apigatewayv2_client=None,
            mapper=DataToJsonMapper(),
            consumer=StringConsumerJsonOutput(),
        )
        endpoint_producer.produce()
        expected_output = [
            call(
                '[\n  {\n    "LogicalResourceId": "HelloWorldFunction",\n    "PhysicalResourceId": "-",\n    "CloudEndpoint": "-",\n    "Methods": "-"\n  },\n  {\n    "LogicalResourceId": "TestResource2",\n    "PhysicalResourceId": "-",\n    "CloudEndpoint": "-",\n    "Methods": []\n  },\n  {\n    "LogicalResourceId": "TestResource5",\n    "PhysicalResourceId": "-",\n    "CloudEndpoint": "-",\n    "Methods": []\n  },\n  {\n    "LogicalResourceId": "TestResource4",\n    "PhysicalResourceId": "-",\n    "CloudEndpoint": "-",\n    "Methods": []\n  },\n  {\n    "LogicalResourceId": "ServerlessRestApi",\n    "PhysicalResourceId": "-",\n    "CloudEndpoint": "-",\n    "Methods": [\n      "/hello2[\'get, put\']",\n      "/hello[\'get\']"\n    ]\n  }\n]'
            )
        ]
        self.assertEqual(patched_click_echo.call_args_list, expected_output)

    @patch("samcli.commands.list.json_consumer.click.echo")
    @patch("samcli.commands.list.json_consumer.click.get_current_context")
    @patch("samcli.lib.list.endpoints.endpoints_producer.get_template_data")
    @patch("samcli.lib.list.endpoints.endpoints_producer.EndpointsProducer.get_translated_dict")
    @patch("samcli.lib.list.endpoints.endpoints_producer.EndpointsProducer.get_resources_info")
    @patch("samcli.lib.list.endpoints.endpoints_producer.EndpointsProducer.get_function_url")
    @patch("samcli.lib.list.endpoints.endpoints_producer.EndpointsProducer.get_stage_list")
    def test_produce_has_stack_name_(
        self,
        mock_get_stages_list,
        mock_get_function_url,
        mock_get_resources_info,
        mock_get_translated_dict,
        mock_get_template_data,
        patched_click_get_current_context,
        patched_click_echo,
    ):
        mock_get_stages_list.return_value = ["testStage"]
        mock_get_function_url.return_value = "test.function.url"
        mock_get_resources_info.return_value = SAM_APP_HELLO_RETURN_RESPONSE
        mock_get_template_data.return_value = {}
        mock_get_translated_dict.return_value = TRANSLATED_DICT_RETURN_WITH_APIS

        stacks = SamLocalStackProvider.get_stacks(
            template_file="", template_dictionary=mock_get_translated_dict.return_value
        )
        endpoint_producer = EndpointsProducer(
            stack_name="sam-app-hello6",
            region="us-east-1",
            profile=None,
            template_file=None,
            cloudformation_client=None,
            iam_client=None,
            cloudcontrol_client=None,
            apigateway_client=None,
            apigatewayv2_client=None,
            mapper=DataToJsonMapper(),
            consumer=StringConsumerJsonOutput(),
        )
        endpoint_producer.produce()
        expected_output = [
            call(
                '[\n  {\n    "LogicalResourceId": "HelloWorldFunction",\n    "PhysicalResourceId": "sam-app-hello6-HelloWorldFunction-testID",\n    "CloudEndpoint": "test.function.url",\n    "Methods": "-"\n  },\n  {\n    "LogicalResourceId": "ServerlessRestApi",\n    "PhysicalResourceId": "jwompba769",\n    "CloudEndpoint": [\n      "https://jwompba769.execute-api.us-east-1.amazonaws.com/testStage"\n    ],\n    "Methods": [\n      "/hello2[\'get, put\']",\n      "/hello[\'get\']"\n    ]\n  },\n  {\n    "LogicalResourceId": "TestResource2",\n    "PhysicalResourceId": "erj31jdyw5",\n    "CloudEndpoint": [\n      "https://erj31jdyw5.execute-api.us-east-1.amazonaws.com/testStage"\n    ],\n    "Methods": []\n  },\n  {\n    "LogicalResourceId": "TestResource4",\n    "PhysicalResourceId": "5u9ekr1d32",\n    "CloudEndpoint": [\n      "https://5u9ekr1d32.execute-api.us-east-1.amazonaws.com/testStage"\n    ],\n    "Methods": []\n  },\n  {\n    "LogicalResourceId": "test_apigw_restapi",\n    "PhysicalResourceId": "testPID",\n    "CloudEndpoint": [\n      "https://test.custom.bpmapping.domain"\n    ],\n    "Methods": []\n  },\n  {\n    "LogicalResourceId": "TestResource5",\n    "PhysicalResourceId": "-",\n    "CloudEndpoint": "-",\n    "Methods": []\n  }\n]'
            )
        ]
        self.assertEqual(patched_click_echo.call_args_list, expected_output)
