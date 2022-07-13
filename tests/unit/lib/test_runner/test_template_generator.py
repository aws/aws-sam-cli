from botocore.exceptions import ClientError
from unittest.mock import patch
from unittest import TestCase
from samcli.lib.test_runner.test_runner_template_generator import generate_test_runner_template_string
from samcli.commands.exceptions import TestRunnerTemplateGenerationException


class Test_TemplateGenerator(TestCase):
    def setUp(self):
        self.maxDiff = None
        with open("samcli/lib/test_runner/base_template.j2") as jinja_template:
            self.jinja_template = jinja_template.read()

        self.test_params = {
            "boto_client_provider": None,  # Patched
            "jinja_base_template": self.jinja_template,
            "s3_bucket_name": "cloud-test-bucket-unique-name",
            "image_uri": "123456789123.dkr.ecr.us-east-1.amazonaws.com/cloud-test-repo",
            "tag_filters": [{"Key": "Test_Key", "Values": ["Test_Value"]}],
        }

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
            "\n",
            "    TaskDefinition:\n",
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
            "                  Image: 123456789123.dkr.ecr.us-east-1.amazonaws.com/cloud-test-repo\n",
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
            "            BucketName: cloud-test-bucket-unique-name",
        ]

    def do_compare(self, resource_arn, expected_actions, query_tagging_api_patch):
        query_tagging_api_patch.return_value = [
            {
                "ResourceARN": resource_arn,
            }
        ]
        result = generate_test_runner_template_string(**self.test_params)

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

    @patch("samcli.lib.test_runner.test_runner_template_generator._query_tagging_api")
    def test_lambda_function(self, query_tagging_api_patch):
        resource_arn = "arn:aws:lambda:us-east-1:123456789123:function:lambda-sample-SampleLambda-KWsMLA204T0i"
        expected_actions = ["                               # - lambda:InvokeFunction\n"]
        self.do_compare(
            resource_arn,
            expected_actions,
            query_tagging_api_patch,
        )

    @patch("samcli.lib.test_runner.test_runner_template_generator._query_tagging_api")
    def test_sqs_queue(self, query_tagging_api_patch):
        resource_arn = "arn:aws:sqs:us-east-2:444455556666:queue1"
        expected_actions = ["                               # - sqs:SendMessage\n"]
        self.do_compare(
            resource_arn,
            expected_actions,
            query_tagging_api_patch,
        )

    @patch("samcli.lib.test_runner.test_runner_template_generator._query_tagging_api")
    def test_s3_bucket(self, query_tagging_api_patch):
        resource_arn = "arn:aws:s3:::my-very-big-s3-bucket"
        expected_actions = [
            "                               # - s3:PutObject\n",
            "                               # - s3:GetObject\n",
        ]
        self.do_compare(
            resource_arn,
            expected_actions,
            query_tagging_api_patch,
        )

    @patch("samcli.lib.test_runner.test_runner_template_generator._query_tagging_api")
    def test_dynamodb_table(self, query_tagging_api_patch):
        resource_arn = "arn:aws:dynamodb:us-east-1:123456789012:table/Books"
        expected_actions = [
            "                               # - dynamodb:GetItem\n",
            "                               # - dynamodb:PutItem\n",
        ]
        self.do_compare(
            resource_arn,
            expected_actions,
            query_tagging_api_patch,
        )

    @patch("samcli.lib.test_runner.test_runner_template_generator._query_tagging_api")
    def test_step_function(self, query_tagging_api_patch):
        resource_arn = "arn:aws:states:us-east-1:123456789012:stateMachine:stateMachineName"
        expected_actions = [
            "                               # - stepfunction:StartExecution\n",
            "                               # - stepfunction:StopExecution\n",
        ]
        self.do_compare(
            resource_arn,
            expected_actions,
            query_tagging_api_patch,
        )

    @patch("samcli.lib.test_runner.test_runner_template_generator._query_tagging_api")
    def test_no_iam_actions_supported(self, query_tagging_api_patch):
        resource_arn = "arn:aws:logs:us-west-1:123456789012:log-group:/mystack-testgroup-12ABC1AB12A1:*"
        expected_actions = []
        self.do_compare(
            resource_arn,
            expected_actions,
            query_tagging_api_patch,
        )

    @patch("samcli.lib.test_runner.test_runner_template_generator._query_tagging_api")
    def test_apigw_httpapi(self, query_tagging_api_patch):
        query_tagging_api_patch.return_value = [
            {
                "ResourceARN": "arn:aws-us-gov:apigateway:us-west-1::/apis/4p1000",
            }
        ]

        result = generate_test_runner_template_string(**self.test_params)

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

    @patch("samcli.lib.test_runner.test_runner_template_generator._query_tagging_api")
    def test_apigw_restapi(self, query_tagging_api_patch):
        query_tagging_api_patch.return_value = [
            {
                "ResourceARN": "arn:aws-us-gov:apigateway:us-west-1::/restapis/r3st4p1",
            }
        ]

        result = generate_test_runner_template_string(**self.test_params)

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

    @patch("samcli.lib.test_runner.test_runner_template_generator._query_tagging_api")
    def test_multiple_generated_statements(self, query_tagging_api_patch):
        arn_1 = "arn:aws:states:us-east-1:123456789012:stateMachine:stateMachineName"
        arn_2 = "arn:aws:s3:::my-very-big-s3-bucket"

        query_tagging_api_patch.return_value = [
            {"ResourceARN": arn_1},
            {"ResourceARN": arn_2},
        ]

        result = generate_test_runner_template_string(**self.test_params)

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

    @patch("samcli.lib.test_runner.test_runner_template_generator._query_tagging_api")
    def test_empty_tag_api_query_response(self, query_tagging_api_patch):
        query_tagging_api_patch.return_value = []

        with self.assertRaises(TestRunnerTemplateGenerationException):
            generate_test_runner_template_string(**self.test_params)

    @patch("samcli.lib.test_runner.test_runner_template_generator._query_tagging_api")
    def test_failed_tag_api_query(self, query_tagging_api_patch):

        client_error_response = {"Error": {"Code": "Error Code", "Message": "Error Message"}}

        query_tagging_api_patch.side_effect = ClientError(
            error_response=client_error_response, operation_name="get_resources"
        )

        with self.assertRaises(TestRunnerTemplateGenerationException):
            generate_test_runner_template_string(**self.test_params)

    def test_no_tag_supplied(self):

        no_tags_params = {
            "boto_client_provider": None,  # Patched
            "jinja_base_template": self.jinja_template,
            "s3_bucket_name": "cloud-test-bucket-unique-name",
            "image_uri": "123456789123.dkr.ecr.us-east-1.amazonaws.com/cloud-test-repo",
            "tag_filters": None,
        }

        result = generate_test_runner_template_string(**no_tags_params)

        expected_result = "".join(
            self.generated_template_expected_first_half + self.generated_template_expected_second_half
        )

        self.assertEqual(result, expected_result)

    @patch("samcli.lib.test_runner.test_runner_template_generator._query_tagging_api")
    def test_unexpected_tag_api_response(self, query_tagging_api_patch):

        query_tagging_api_patch.return_value = None

        with self.assertRaises(TestRunnerTemplateGenerationException):
            generate_test_runner_template_string(**self.test_params)
