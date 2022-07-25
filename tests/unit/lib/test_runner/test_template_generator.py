import unittest
from unittest.mock import Mock, patch
from unittest import TestCase
import jinja2
from samcli.lib.test_runner.test_runner_template_generator import FargateRunnerCFNTemplateGenerator
from samcli.commands.exceptions import TestRunnerTemplateGenerationException


class Test_TemplateGenerator(TestCase):

    TEST_BUCKET_NAME = "test-bucket"
    TEST_IMAGE_URI = "test-image-uri"

    def setUp(self):
        self.maxDiff = None
        self.template_generator = FargateRunnerCFNTemplateGenerator([])

        # Mock the bucket name, since it will contain a random UUID
        _get_default_bucket_name_mock = Mock()
        _get_default_bucket_name_mock.return_value = self.TEST_BUCKET_NAME
        self.template_generator._get_default_bucket_name = _get_default_bucket_name_mock

        # To avoid repeated lines:
        # These parts of the template will be the same no matter what resource is being tested
        # In between will be the generated IAM policy statments, which will depend on the resource being tested
        self.generated_template_expected_first_half = [
            "AWSTemplateFormatVersion: 2010-09-09\n",
            "Description: Sample Template to deploy and run test container with Fargate\n",
            "Resources:\n",
            "\n",
            "    ContainerIAMRole:\n",
            "        Type: AWS::IAM::Role\n",
            "        Properties:\n",
            "            Description: Allows Fargate task to access S3 bucket to download tests and upload results\n",
            "            AssumeRolePolicyDocument:\n",
            "                Version: 2012-10-17\n",
            "                Statement:\n",
            "                    - Effect: Allow\n",
            "                      Principal:\n",
            "                          Service:\n",
            "                              - ecs-tasks.amazonaws.com\n",
            "                      Action:\n",
            "                          - sts:AssumeRole\n",
            "            Policies:\n",
            "                - PolicyName: ContainerPermissions\n",
            "                  PolicyDocument:\n",
            "                      Version: 2012-10-17\n",
            "                      Statement:\n",
            "                          - Sid: S3BucketAccess\n",
            "                            Effect: Allow\n",
            "                            Action:\n",
            "                                - s3:PutObject\n",
            "                                - s3:GetObject\n",
            "                            Resource: !Sub\n",
            "                                - arn:aws:s3:::${bucket}/*\n",
            "                                - bucket: !Ref S3Bucket\n",
        ]
        self.generated_template_expected_second_half = [
            "\n" "    TaskDefinition:\n",
            "        Type: AWS::ECS::TaskDefinition\n",
            "        Properties:\n",
            "            RequiresCompatibilities:\n",
            "                - FARGATE\n",
            "            ExecutionRoleArn: !Sub arn:aws:iam::${AWS::AccountId}:role/ecsTaskExecutionRole\n",
            "            TaskRoleArn: !Ref ContainerIAMRole\n",
            "            Cpu: 256\n",
            "            Memory: 512\n",
            "            NetworkMode: awsvpc\n",
            "            ContainerDefinitions:\n",
            "                - Name: cloud-test-python-container\n",
            f"                  Image: {self.TEST_IMAGE_URI}\n",
            "                  PortMappings:\n",
            "                      - ContainerPort: 8080\n",
            "                        Protocol: tcp\n",
            "                  LogConfiguration:\n",
            "                      LogDriver: awslogs\n",
            "                      Options:\n",
            "                          awslogs-region: !Ref AWS::Region\n",
            "                          awslogs-group: !Ref LogGroup\n",
            "                          awslogs-stream-prefix: ecs\n",
            "\n",
            "    LogGroup:\n",
            "        Type: AWS::Logs::LogGroup\n",
            "        Properties:\n",
            "            LogGroupName: cloud-test-loggroup\n",
            "\n",
            "    ECSCluster:\n",
            "        Type: AWS::ECS::Cluster\n",
            "        Properties:\n",
            "            ClusterName: cloud-test-fargate-cluster\n",
            "\n",
            "    S3Bucket:\n",
            "        Type: AWS::S3::Bucket\n",
            "        Properties:\n",
            f"            BucketName: {self.TEST_BUCKET_NAME}",
        ]

    def do_compare(
        self,
        resource_arn,
        expected_actions,
    ):
        self.template_generator.resource_arn_list = [resource_arn]
        result = self.template_generator.generate_test_runner_template_string(self.TEST_IMAGE_URI)
        expected_statements = [
            "                          - Effect: Allow\n",
            "                            Action:\n",
        ]
        expected_statements.extend(expected_actions)
        expected_statements.append(f"                            Resource: {resource_arn}\n")

        expected_result = "".join(
            self.generated_template_expected_first_half
            + expected_statements
            + self.generated_template_expected_second_half
        )
        self.assertEqual(result, expected_result)

    def test_lambda_function(self):
        resource_arn = "arn:aws:lambda:us-east-1:123456789123:function:lambda-sample-SampleLambda-KWsMLA204T0i"
        expected_actions = ["                               # - lambda:InvokeFunction\n"]
        self.do_compare(resource_arn, expected_actions)

    def test_sqs_queue(self):
        resource_arn = "arn:aws:sqs:us-east-2:444455556666:queue1"
        expected_actions = ["                               # - sqs:SendMessage\n"]
        self.do_compare(
            resource_arn,
            expected_actions,
        )

    def test_s3_bucket(self):
        resource_arn = "arn:aws:s3:::my-very-big-s3-bucket"
        expected_actions = [
            "                               # - s3:PutObject\n",
            "                               # - s3:GetObject\n",
        ]
        self.do_compare(resource_arn, expected_actions)

    def test_dynamodb_table(self):
        resource_arn = "arn:aws:dynamodb:us-east-1:123456789012:table/Books"
        expected_actions = [
            "                               # - dynamodb:GetItem\n",
            "                               # - dynamodb:PutItem\n",
        ]
        self.do_compare(resource_arn, expected_actions)

    def test_step_function(self):
        resource_arn = "arn:aws:states:us-east-1:123456789012:stateMachine:stateMachineName"
        expected_actions = [
            "                               # - stepfunction:StartExecution\n",
            "                               # - stepfunction:StopExecution\n",
        ]
        self.do_compare(resource_arn, expected_actions)

    def test_no_iam_actions_supported(self):
        resource_arn = "arn:aws:logs:us-west-1:123456789012:log-group:/mystack-testgroup-12ABC1AB12A1:*"
        expected_actions = []
        self.do_compare(resource_arn, expected_actions)

    def test_apigw_httpapi(self):
        self.template_generator.resource_arn_list = ["arn:aws-us-gov:apigateway:us-west-1::/apis/4p1000"]

        result = self.template_generator.generate_test_runner_template_string(self.TEST_IMAGE_URI)

        expected_statements = [
            "                          - Effect: Allow\n",
            "                            Action:\n",
            "                               # - execute-api:Invoke\n",
            "                            Resource: !Sub arn:${AWS::Partition}:execute-api:${AWS::Region}:${AWS::AccountId}:4p1000/*/GET/*\n",
        ]

        expected_result = "".join(
            self.generated_template_expected_first_half
            + expected_statements
            + self.generated_template_expected_second_half
        )
        self.assertEqual(result, expected_result)

    def test_apigw_restapi(self):
        self.template_generator.resource_arn_list = [
            "arn:aws-us-gov:apigateway:us-west-1::/restapis/r3st4p1",
        ]

        result = self.template_generator.generate_test_runner_template_string(self.TEST_IMAGE_URI)

        expected_statements = [
            "                          - Effect: Allow\n",
            "                            Action:\n",
            "                               # - execute-api:Invoke\n",
            "                            Resource: !Sub arn:${AWS::Partition}:execute-api:${AWS::Region}:${AWS::AccountId}:r3st4p1/*/GET/*\n",
        ]

        expected_result = "".join(
            self.generated_template_expected_first_half
            + expected_statements
            + self.generated_template_expected_second_half
        )
        self.assertEqual(result, expected_result)

    def test_multiple_generated_statements(self):
        arn_1 = "arn:aws:states:us-east-1:123456789012:stateMachine:stateMachineName"
        arn_2 = "arn:aws:s3:::my-very-big-s3-bucket"

        self.template_generator.resource_arn_list = [arn_1, arn_2]

        result = self.template_generator.generate_test_runner_template_string(self.TEST_IMAGE_URI)

        expected_statements = [
            "                          - Effect: Allow\n",
            "                            Action:\n",
            "                               # - stepfunction:StartExecution\n",
            "                               # - stepfunction:StopExecution\n",
            f"                            Resource: {arn_1}\n",
            "                          - Effect: Allow\n",
            "                            Action:\n",
            "                               # - s3:PutObject\n",
            "                               # - s3:GetObject\n",
            f"                            Resource: {arn_2}\n",
        ]

        expected_result = "".join(
            self.generated_template_expected_first_half
            + expected_statements
            + self.generated_template_expected_second_half
        )
        self.assertEqual(result, expected_result)

    def test_iam_resource(self):
        self.template_generator.resource_arn_list = ["arn:aws:iam::123456789012:root"]

        result = self.template_generator.generate_test_runner_template_string(self.TEST_IMAGE_URI)

        expected_statements = []

        expected_result = "".join(
            self.generated_template_expected_first_half
            + expected_statements
            + self.generated_template_expected_second_half
        )
        self.assertEqual(result, expected_result)

    def test_sts_resource(self):
        self.template_generator.resource_arn_list = ["arn:aws:sts::123456789012:federated-user/user-name "]

        result = self.template_generator.generate_test_runner_template_string(self.TEST_IMAGE_URI)
        expected_statements = []

        expected_result = "".join(
            self.generated_template_expected_first_half
            + expected_statements
            + self.generated_template_expected_second_half
        )
        self.assertEqual(result, expected_result)

    def test_statement_jinja_exception(self):

        def faulty_create_iam_statement_string(obj, arn):
            raise jinja2.exceptions.TemplateError("Template render failed for some reason!")

        with unittest.mock.patch.object(FargateRunnerCFNTemplateGenerator, '_create_iam_statement_string', new=faulty_create_iam_statement_string):
            self.template_generator.resource_arn_list = ["arn:aws:lambda:us-east-1:123456789123:function:valid-lambda-arn"]
            with self.assertRaises(TestRunnerTemplateGenerationException):
                self.template_generator.generate_test_runner_template_string(self.TEST_IMAGE_URI)

    def test_no_arns_supplied(self):
        result = self.template_generator.generate_test_runner_template_string(self.TEST_IMAGE_URI)
        expected_statements = []

        expected_result = "".join(
            self.generated_template_expected_first_half
            + expected_statements
            + self.generated_template_expected_second_half
        )
        self.assertEqual(result, expected_result)

    def test_jinja_template_not_found(self):

        def faulty_get_jinja_template_string(obj):
            raise FileNotFoundError()

        with unittest.mock.patch.object(FargateRunnerCFNTemplateGenerator, '_get_jinja_template_string', new=faulty_get_jinja_template_string):
            self.template_generator.resource_arn_list = ["arn:aws:lambda:us-east-1:123456789123:function:valid-lambda-arn"]
            with self.assertRaises(TestRunnerTemplateGenerationException):
                self.template_generator.generate_test_runner_template_string(self.TEST_IMAGE_URI)
