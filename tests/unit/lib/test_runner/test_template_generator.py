import unittest
import json
from unittest.mock import patch
from samcli.lib.test_runner.test_runner_template_generator import generateTestRunnerTemplateString
from samcli.lib.test_runner.base_template import base_template_json


class Test_TemplateGenerator(unittest.TestCase):
    def setUp(self):

        self.test_params = {
            "jinjaTemplateJsonString": json.dumps(base_template_json),
            "bucketName": "cloud-test-bucket-unique-name",
            "ecsTaskExecRoleArn": "arn:aws:iam::123456789123:role/ecsTaskExecutionRole",
            "imageUri": "123456789123.dkr.ecr.us-east-1.amazonaws.com/cloud-test-repo",
            "vpcId": "vpc-xxxxxxxxxxxxxxxxx",
            "tagFilters": [{"Key": "Test_Key", "Values": ["Test_Value"]}],
        }

        # To avoid repeated lines:
        # These parts of the template will be the same no matter what resource is being tested
        # In between will be the generated IAM policy statments, which will depend on the resource being tested
        self.generatedTemplateExpectedFirstHalf = [
            "AWSTemplateFormatVersion: 2010-09-09\n",
            "Description: Sample Template to deploy and run test container with Fargate\n",
            "Resources:\n",
            "  ContainerIAMRole:\n",
            "    Type: AWS::IAM::Role\n",
            "    Properties:\n",
            "      Description: Allows Fargate task to access S3 bucket to download tests and upload results\n",
            "      AssumeRolePolicyDocument:\n",
            "        Version: 2012-10-17\n",
            "        Statement:\n",
            "          - Effect: Allow\n",
            "            Principal:\n",
            "              Service:\n",
            "                - ecs-tasks.amazonaws.com\n",
            "            Action:\n",
            "              - sts:AssumeRole\n",
            "      Policies:\n",
            "        - PolicyName: ContainerPermissions\n",
            "          PolicyDocument:\n",
            "            Version: 2012-10-17\n",
            "            Statement:\n",
            "              - Sid: S3BucketAccess\n",
            "                Effect: Allow\n",
            "                Action:\n",
            "                  - s3:PutObject\n",
            "                  - s3:GetObject\n",
            "                Resource: !Sub\n",
            "                  - arn:aws:s3:::${bucket}/*\n",
            "                  - bucket: !Ref S3Bucket\n",
        ]
        self.generatedTemplateExpectedSecondHalf = [
            "  TaskDefinition:\n",
            "    Type: AWS::ECS::TaskDefinition\n",
            "    Properties:\n",
            "      RequiresCompatibilities:\n",
            "        - FARGATE\n",
            "      ExecutionRoleArn: arn:aws:iam::123456789123:role/ecsTaskExecutionRole\n",
            "      TaskRoleArn: !Ref ContainerIAMRole\n",
            "      Cpu: 256\n",
            "      Memory: 512\n",
            "      NetworkMode: awsvpc\n",
            "      ContainerDefinitions:\n",
            "        - Name: cloud-test-python-container\n",
            "          Image: 123456789123.dkr.ecr.us-east-1.amazonaws.com/cloud-test-repo\n",
            "          PortMappings:\n",
            "            - ContainerPort: 8080\n",
            "              Protocol: tcp\n",
            "          LogConfiguration:\n",
            "            LogDriver: awslogs\n",
            "            Options:\n",
            "              awslogs-region: !Ref AWS::Region\n",
            "              awslogs-group: !Ref LogGroup\n",
            "              awslogs-stream-prefix: ecs\n",
            "  LogGroup:\n",
            "    Type: AWS::Logs::LogGroup\n",
            "    Properties:\n",
            "      LogGroupName: cloud-test-loggroup\n",
            "  ECSCluster:\n",
            "    Type: AWS::ECS::Cluster\n",
            "    Properties:\n",
            "      ClusterName: cloud-test-fargate-cluster\n",
            "  SecurityGroup:\n",
            "    Type: AWS::EC2::SecurityGroup\n",
            "    Properties:\n",
            "      GroupDescription: cloud-test security group\n",
            "      GroupName: cloud-test-security-group\n",
            "      VpcId: vpc-xxxxxxxxxxxxxxxxx\n",
            "  S3Bucket:\n",
            "    Type: AWS::S3::Bucket\n",
            "    Properties:\n",
            "      BucketName: cloud-test-bucket-unique-name\n",
        ]

    @patch("samcli.lib.test_runner.test_runner_template_generator.__queryTaggingApi")
    def test_lambda_function(self, queryTaggingApiPatch):

        queryTaggingApiPatch.return_value = {
            "ResourceTagMappingList": [
                {
                    "ResourceARN": "arn:aws:lambda:us-east-1:123456789123:function:lambda-sample-SampleLambda-KWsMLA204T0i",
                }
            ]
        }

        result = generateTestRunnerTemplateString(**self.test_params)

        expected_statements = [
            "              - Effect: Allow\n",
            "                Action:\n",
            "                  - placeholder:DeleteThis\n",
            "                  # - lambda:InvokeFunction\n",
            "                Resource: arn:aws:lambda:us-east-1:123456789123:function:lambda-sample-SampleLambda-KWsMLA204T0i\n",
        ]

        expected_result = "".join(
            self.generatedTemplateExpectedFirstHalf + expected_statements + self.generatedTemplateExpectedSecondHalf
        )
        self.assertEqual(result, expected_result)

    @patch("samcli.lib.test_runner.test_runner_template_generator.__queryTaggingApi")
    def test_apigw_httpapi(self, queryTaggingApiPatch):
        queryTaggingApiPatch.return_value = {
            "ResourceTagMappingList": [
                {
                    "ResourceARN": "arn:aws-us-gov:apigateway:us-west-1::/apis/4p1000",
                }
            ]
        }

        result = generateTestRunnerTemplateString(**self.test_params)

        expected_statements = [
            "              - Effect: Allow\n",
            "                Action:\n",
            "                  - placeholder:DeleteThis\n",
            "                  # - execute-api:Invoke\n",
            "                Resource: !Sub arn:${AWS::Partition}:execute-api:${AWS::Region}:${AWS::AccountId}:4p1000/<STAGE>/GET/<RESOURCE_PATH>\n",
        ]

        expected_result = "".join(
            self.generatedTemplateExpectedFirstHalf + expected_statements + self.generatedTemplateExpectedSecondHalf
        )
        self.assertEqual(result, expected_result)

    @patch("samcli.lib.test_runner.test_runner_template_generator.__queryTaggingApi")
    def test_apigw_restapi(self, queryTaggingApiPatch):
        queryTaggingApiPatch.return_value = {
            "ResourceTagMappingList": [
                {
                    "ResourceARN": "arn:aws-us-gov:apigateway:us-west-1::/restapis/r3st4p1",
                }
            ]
        }

        result = generateTestRunnerTemplateString(**self.test_params)

        expected_statements = [
            "              - Effect: Allow\n",
            "                Action:\n",
            "                  - placeholder:DeleteThis\n",
            "                  # - execute-api:Invoke\n",
            "                Resource: !Sub arn:${AWS::Partition}:execute-api:${AWS::Region}:${AWS::AccountId}:r3st4p1/<STAGE>/GET/<RESOURCE_PATH>\n",
        ]

        expected_result = "".join(
            self.generatedTemplateExpectedFirstHalf + expected_statements + self.generatedTemplateExpectedSecondHalf
        )
        self.assertEqual(result, expected_result)

    @patch("samcli.lib.test_runner.test_runner_template_generator.__queryTaggingApi")
    def test_sqs_queue(self, queryTaggingApiPatch):
        queryTaggingApiPatch.return_value = {
            "ResourceTagMappingList": [
                {
                    "ResourceARN": "arn:aws:sqs:us-east-2:444455556666:queue1",
                }
            ]
        }

        result = generateTestRunnerTemplateString(**self.test_params)

        expected_statements = [
            "              - Effect: Allow\n",
            "                Action:\n",
            "                  - placeholder:DeleteThis\n",
            "                  # - sqs:SendMessage\n",
            "                Resource: arn:aws:sqs:us-east-2:444455556666:queue1\n",
        ]

        expected_result = "".join(
            self.generatedTemplateExpectedFirstHalf + expected_statements + self.generatedTemplateExpectedSecondHalf
        )
        self.maxDiff = None
        self.assertEqual(result, expected_result)

    @patch("samcli.lib.test_runner.test_runner_template_generator.__queryTaggingApi")
    def test_s3_bucket(self, queryTaggingApiPatch):
        queryTaggingApiPatch.return_value = {
            "ResourceTagMappingList": [
                {
                    "ResourceARN": "arn:aws:s3:::my-very-big-s3-bucket",
                }
            ]
        }

        result = generateTestRunnerTemplateString(**self.test_params)

        expected_statements = [
            "              - Effect: Allow\n",
            "                Action:\n",
            "                  - placeholder:DeleteThis\n",
            "                  # - s3:PutObject\n",
            "                  # - s3:GetObject\n",
            "                Resource: arn:aws:s3:::my-very-big-s3-bucket\n",
        ]

        expected_result = "".join(
            self.generatedTemplateExpectedFirstHalf + expected_statements + self.generatedTemplateExpectedSecondHalf
        )
        self.maxDiff = None
        self.assertEqual(result, expected_result)

    @patch("samcli.lib.test_runner.test_runner_template_generator.__queryTaggingApi")
    def test_dynamodb_table(self, queryTaggingApiPatch):
        queryTaggingApiPatch.return_value = {
            "ResourceTagMappingList": [
                {
                    "ResourceARN": "arn:aws:dynamodb:us-east-1:123456789012:table/Books",
                }
            ]
        }

        result = generateTestRunnerTemplateString(**self.test_params)

        expected_statements = [
            "              - Effect: Allow\n",
            "                Action:\n",
            "                  - placeholder:DeleteThis\n",
            "                  # - dynamodb:GetItem\n",
            "                  # - dynamodb:PutItem\n",
            "                Resource: arn:aws:dynamodb:us-east-1:123456789012:table/Books\n",
        ]

        expected_result = "".join(
            self.generatedTemplateExpectedFirstHalf + expected_statements + self.generatedTemplateExpectedSecondHalf
        )
        self.maxDiff = None
        self.assertEqual(result, expected_result)

    @patch("samcli.lib.test_runner.test_runner_template_generator.__queryTaggingApi")
    def test_step_function(self, queryTaggingApiPatch):
        queryTaggingApiPatch.return_value = {
            "ResourceTagMappingList": [
                {
                    "ResourceARN": "arn:aws:states:us-east-1:123456789012:stateMachine:stateMachineName",
                }
            ]
        }

        result = generateTestRunnerTemplateString(**self.test_params)

        expected_statements = [
            "              - Effect: Allow\n",
            "                Action:\n",
            "                  - placeholder:DeleteThis\n",
            "                  # - stepfunction:StartExecution\n",
            "                  # - stepfunction:StopExecution\n",
            "                Resource: arn:aws:states:us-east-1:123456789012:stateMachine:stateMachineName\n",
        ]

        expected_result = "".join(
            self.generatedTemplateExpectedFirstHalf + expected_statements + self.generatedTemplateExpectedSecondHalf
        )
        self.maxDiff = None
        self.assertEqual(result, expected_result)

    @patch("samcli.lib.test_runner.test_runner_template_generator.__queryTaggingApi")
    def test_log_group(self, queryTaggingApiPatch):
        queryTaggingApiPatch.return_value = {
            "ResourceTagMappingList": [
                {
                    "ResourceARN": "arn:aws:logs:us-west-1:123456789012:log-group:/mystack-testgroup-12ABC1AB12A1:*",
                }
            ]
        }

        result = generateTestRunnerTemplateString(**self.test_params)

        expected_statements = [
            "              - Effect: Allow\n",
            "                Action:\n",
            "                  - placeholder:DeleteThis\n",
            "                Resource: arn:aws:logs:us-west-1:123456789012:log-group:/mystack-testgroup-12ABC1AB12A1:*\n",
        ]

        expected_result = "".join(
            self.generatedTemplateExpectedFirstHalf + expected_statements + self.generatedTemplateExpectedSecondHalf
        )
        self.assertEqual(result, expected_result)
