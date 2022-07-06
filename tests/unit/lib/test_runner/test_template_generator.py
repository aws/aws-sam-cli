import unittest
from unittest.mock import patch
from samcli.lib.test_runner.test_runner_template_generator import generate_test_runner_template_string


class Test_TemplateGenerator(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        with open("samcli/lib/test_runner/base_template.j2") as jinja_template:
            self.test_params = {
                "jinja_base_template": jinja_template.read(),
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
            "    LogGroup:\n",
            "        Type: AWS::Logs::LogGroup\n",
            "        Properties:\n",
            "            LogGroupName: cloud-test-loggroup\n",
            "    ECSCluster:\n",
            "        Type: AWS::ECS::Cluster\n",
            "        Properties:\n",
            "            ClusterName: cloud-test-fargate-cluster\n",
            "    S3Bucket:\n",
            "        Type: AWS::S3::Bucket\n",
            "        Properties:\n",
            "            BucketName: cloud-test-bucket-unique-name",
        ]

    @patch("samcli.lib.test_runner.test_runner_template_generator._query_tagging_api")
    def test_lambda_function(self, query_tagging_api_patch):

        query_tagging_api_patch.return_value = [
            {
                "ResourceARN": "arn:aws:lambda:us-east-1:123456789123:function:lambda-sample-SampleLambda-KWsMLA204T0i",
            }
        ]

        result = generate_test_runner_template_string(**self.test_params)

        expected_statements = [
            "                          - Effect: Allow\n",
            "                            Action:\n",
            "                               # - lambda:InvokeFunction\n",
            "                            Resource: arn:aws:lambda:us-east-1:123456789123:function:lambda-sample-SampleLambda-KWsMLA204T0i\n",
        ]

        expected_result = "".join(
            self.generated_template_expected_first_half
            + expected_statements
            + self.generated_template_expected_second_half
        )
        self.assertEqual(result, expected_result)

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
            "                            Resource: !Sub arn:${AWS::Partition}:execute-api:${AWS::Region}:${AWS::AccountId}:4p1000/<STAGE>/GET/<RESOURCE_PATH>\n",
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
            "                            Resource: !Sub arn:${AWS::Partition}:execute-api:${AWS::Region}:${AWS::AccountId}:r3st4p1/<STAGE>/GET/<RESOURCE_PATH>\n",
        ]

        expected_result = "".join(
            self.generated_template_expected_first_half
            + expected_statements
            + self.generated_template_expected_second_half
        )
        self.assertEqual(result, expected_result)

    @patch("samcli.lib.test_runner.test_runner_template_generator._query_tagging_api")
    def test_sqs_queue(self, query_tagging_api_patch):
        query_tagging_api_patch.return_value = [
            {
                "ResourceARN": "arn:aws:sqs:us-east-2:444455556666:queue1",
            }
        ]

        result = generate_test_runner_template_string(**self.test_params)

        expected_statements = [
            "                          - Effect: Allow\n",
            "                            Action:\n",
            "                               # - sqs:SendMessage\n",
            "                            Resource: arn:aws:sqs:us-east-2:444455556666:queue1\n",
        ]

        expected_result = "".join(
            self.generated_template_expected_first_half
            + expected_statements
            + self.generated_template_expected_second_half
        )
        self.maxDiff = None
        self.assertEqual(result, expected_result)

    @patch("samcli.lib.test_runner.test_runner_template_generator._query_tagging_api")
    def test_s3_bucket(self, query_tagging_api_patch):
        query_tagging_api_patch.return_value = [
            {
                "ResourceARN": "arn:aws:s3:::my-very-big-s3-bucket",
            }
        ]

        result = generate_test_runner_template_string(**self.test_params)

        expected_statements = [
            "                          - Effect: Allow\n",
            "                            Action:\n",
            "                               # - s3:PutObject\n",
            "                               # - s3:GetObject\n",
            "                            Resource: arn:aws:s3:::my-very-big-s3-bucket\n",
        ]

        expected_result = "".join(
            self.generated_template_expected_first_half
            + expected_statements
            + self.generated_template_expected_second_half
        )
        self.maxDiff = None
        self.assertEqual(result, expected_result)

    @patch("samcli.lib.test_runner.test_runner_template_generator._query_tagging_api")
    def test_dynamodb_table(self, query_tagging_api_patch):
        query_tagging_api_patch.return_value = [
            {
                "ResourceARN": "arn:aws:dynamodb:us-east-1:123456789012:table/Books",
            }
        ]

        result = generate_test_runner_template_string(**self.test_params)

        expected_statements = [
            "                          - Effect: Allow\n",
            "                            Action:\n",
            "                               # - dynamodb:GetItem\n",
            "                               # - dynamodb:PutItem\n",
            "                            Resource: arn:aws:dynamodb:us-east-1:123456789012:table/Books\n",
        ]

        expected_result = "".join(
            self.generated_template_expected_first_half
            + expected_statements
            + self.generated_template_expected_second_half
        )
        self.maxDiff = None
        self.assertEqual(result, expected_result)

    @patch("samcli.lib.test_runner.test_runner_template_generator._query_tagging_api")
    def test_step_function(self, query_tagging_api_patch):
        query_tagging_api_patch.return_value = [
            {
                "ResourceARN": "arn:aws:states:us-east-1:123456789012:stateMachine:stateMachineName",
            }
        ]

        result = generate_test_runner_template_string(**self.test_params)

        expected_statements = [
            "                          - Effect: Allow\n",
            "                            Action:\n",
            "                               # - stepfunction:StartExecution\n",
            "                               # - stepfunction:StopExecution\n",
            "                            Resource: arn:aws:states:us-east-1:123456789012:stateMachine:stateMachineName\n",
        ]

        expected_result = "".join(
            self.generated_template_expected_first_half
            + expected_statements
            + self.generated_template_expected_second_half
        )
        self.maxDiff = None
        self.assertEqual(result, expected_result)

    @patch("samcli.lib.test_runner.test_runner_template_generator._query_tagging_api")
    def test_no_iam_actions_supported(self, query_tagging_api_patch):
        query_tagging_api_patch.return_value = [
            {
                "ResourceARN": "arn:aws:logs:us-west-1:123456789012:log-group:/mystack-testgroup-12ABC1AB12A1:*",
            }
        ]

        result = generate_test_runner_template_string(**self.test_params)

        expected_statements = [
            "                          - Effect: Allow\n",
            "                            Action:\n",
            "                            Resource: arn:aws:logs:us-west-1:123456789012:log-group:/mystack-testgroup-12ABC1AB12A1:*\n",
        ]

        expected_result = "".join(
            self.generated_template_expected_first_half
            + expected_statements
            + self.generated_template_expected_second_half
        )
        self.assertEqual(result, expected_result)

    @patch("samcli.lib.test_runner.test_runner_template_generator._query_tagging_api")
    def test_failed_tag_api_query(self, query_tagging_api_patch):
        query_tagging_api_patch.return_value = None

        result = generate_test_runner_template_string(**self.test_params)

        expected_statements = [
            "                          # Failed to query tagging api, can't generate IAM permissions for your resources.\n"
        ]

        expected_result = "".join(
            self.generated_template_expected_first_half
            + expected_statements
            + self.generated_template_expected_second_half
        )
        self.assertEqual(result, expected_result)
