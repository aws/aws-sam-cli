import re
import logging
import uuid
from typing import Optional, List, Union

LOG = logging.getLogger(__name__)


class FargateRunnerCFNTemplateGenerator:

    TEST_RUNNER_TEMPLATE_STRING = """AWSTemplateFormatVersion: 2010-09-09
Description: SAM Test Runner Stack, used to deploy and run tests using Fargate
Resources:

    ContainerIAMRole:
        Type: AWS::IAM::Role
        Properties:
            Description: IAM Permissions granted to the Fargate instance so that it can invoke and test deployed resources
            AssumeRolePolicyDocument:
                Version: 2012-10-17
                Statement:
                    - Effect: Allow
                      Principal:
                          Service:
                              - ecs-tasks.amazonaws.com
                      Action:
                          - sts:AssumeRole
            Policies:
                - PolicyName: ContainerPermissions
                  PolicyDocument:
                      Version: 2012-10-17
                      Statement:
                          - Sid: S3BucketAccess
                            Effect: Allow
                            Action:
                                - s3:PutObject
                                - s3:GetObject
                            Resource: !Sub
                                - arn:aws:s3:::${bucket}/*
                                - bucket: !Ref S3Bucket
{{generated_statements}}
    TaskDefinition:
        Type: AWS::ECS::TaskDefinition
        Properties:
            RequiresCompatibilities:
                - FARGATE
            ExecutionRoleArn: !Sub arn:aws:iam::${AWS::AccountId}:role/ecsTaskExecutionRole
            TaskRoleArn: !Ref ContainerIAMRole
            Cpu: 256
            Memory: 512
            NetworkMode: awsvpc
            ContainerDefinitions:
                - Name: cloud-test-python-container
                  Image: {{image_uri}}
                  PortMappings:
                      - ContainerPort: 8080
                        Protocol: tcp
                  LogConfiguration:
                      LogDriver: awslogs
                      Options:
                          awslogs-region: !Ref AWS::Region
                          awslogs-group: !Ref LogGroup
                          awslogs-stream-prefix: ecs

    LogGroup:
        Type: AWS::Logs::LogGroup
        Properties:
            LogGroupName: test-runner-loggroup

    ECSCluster:
        Type: AWS::ECS::Cluster
        Properties:
            ClusterName: test-runner-fargate-cluster

    S3Bucket:
        Type: AWS::S3::Bucket
        Properties:
            BucketName: {{s3_bucket_name}}"""

    def __init__(self, resource_arn_list: Optional[List[str]]):
        self.resource_arn_list = resource_arn_list

    def _extract_api_id_from_arn(self, api_arn: str) -> str:
        """
        Extracts an api id from an HTTP or REST api arn.

        NOTE: https://docs.aws.amazon.com/apigateway/latest/developerguide/arn-format-reference.html

        REST API Arn: `arn:partition:apigateway:region::/restapis/api-id`

        HTTP API Arn: `arn:partition:apigateway:region::/apis/api-id`

        Parameters
        ----------
        api_arn : str
            The arn of the HTTP or REST api from which the api id is extracted.

        Returns
        -------
        str
            The api id from the api arn.
        """

        return api_arn[api_arn.rindex("/") + 1 :]

    def _indent_string(self, input_string: str, tabs: int) -> str:
        return "    " * tabs + input_string

    def _create_iam_statement_string(self, resource_arn: str) -> Union[str, None]:
        """
        Returns an IAM Statement in the form of a YAML string corresponding to the supplied resource ARN.

        The generated Actions are commented out to establish a barrier of consent, preventing customers from accidentally granting permissions that they did not mean to.

        The Action list is empty if there are no IAM Action permissions to generate for the given resource.

        Returns `None` if the `resource_arn` corresponds to an IAM or STS resource.

        Parameters
        ----------
        resource_arn : str
            The arn of the resource for which the IAM statement is generated.

        Returns
        -------
        str:
            An IAM Statement in the form of a YAML string.

            `None` if the `resource_arn` corresponds to an IAM or STS resource.
        """

        # We keep partition and region general to avoid the burden of maintaining new regions & partitions.
        partition_regex = r"[\w-]+"
        region_regex = r"[\w-]+"
        account_regex = r"\d{12}"

        # We want to explcitly avoid generating permissions for IAM or STS resources
        IAM_PREFIX_REGEX = rf"^arn:{partition_regex}:(iam|sts)"

        if re.search(IAM_PREFIX_REGEX, resource_arn):
            LOG.debug("ARN `%s` is for an IAM or STS resource, will not generate permissions.", resource_arn)
            return None

        LAMBDA_FUNCTION_REGEX = rf"^arn:{partition_regex}:lambda:{region_regex}:{account_regex}:function:[\w-]+(:\d+)?$"
        APIGW_API_REGEX = rf"^arn:{partition_regex}:apigateway:{region_regex}::\/apis\/\w+$"
        APIGW_RESTAPI_REGEX = rf"^arn:{partition_regex}:apigateway:{region_regex}::\/restapis\/\w+$"
        SQS_QUEUE_REGEX = rf"^arn:{partition_regex}:sqs:{region_regex}:{account_regex}:[\w-]+$"
        S3_BUCKET_REGEX = rf"^arn:{partition_regex}:s3:::[\w-]+$"
        DYNAMODB_TABLE_REGEX = rf"^arn:{partition_regex}:dynamodb:{region_regex}:{account_regex}:table\/[\w-]+$"
        STEPFUNCTION_REGEX = rf"^arn:{partition_regex}:states:{region_regex}:{account_regex}:stateMachine:[\w-]+$"

        default_permissions_map = {
            LAMBDA_FUNCTION_REGEX: ["lambda:InvokeFunction"],
            APIGW_API_REGEX: ["execute-api:Invoke"],
            APIGW_RESTAPI_REGEX: ["execute-api:Invoke"],
            SQS_QUEUE_REGEX: ["sqs:SendMessage"],
            S3_BUCKET_REGEX: ["s3:PutObject", "s3:GetObject"],
            DYNAMODB_TABLE_REGEX: [
                "dynamodb:GetItem",
                "dynamodb:PutItem",
            ],
            STEPFUNCTION_REGEX: [
                "stepfunction:StartExecution",
                "stepfunction:StopExecution",
            ],
        }

        new_statement_prefix = self._indent_string("  - Effect: Allow\n", 6) + self._indent_string("Action:\n", 7)

        for arn_regex, action_list in default_permissions_map.items():
            if re.search(arn_regex, resource_arn) is not None:
                LOG.debug("Matched ARN `%s` to IAM actions %s", resource_arn, action_list)

                new_statement = new_statement_prefix
                for action in action_list:
                    new_statement += self._indent_string(f"   # - {action}\n", 7)

                # APIGW API IAM Statements:
                # https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-control-access-using-iam-policies-to-invoke-api.html
                if arn_regex in (APIGW_API_REGEX, APIGW_RESTAPI_REGEX):
                    apiId = self._extract_api_id_from_arn(resource_arn)
                    execute_api_arn = (
                        f"!Sub arn:${{AWS::Partition}}:execute-api:${{AWS::Region}}:${{AWS::AccountId}}:{apiId}/*"
                    )

                    return new_statement + self._indent_string(f"Resource: {execute_api_arn}\n", 7)
                else:
                    return new_statement + self._indent_string(f"Resource: {resource_arn}\n", 7)

        # If the supplied ARN is for a resource without any default actions supported
        LOG.debug("Found no match for ARN `%s` to any IAM actions.", resource_arn)
        return new_statement_prefix + self._indent_string(f"Resource: {resource_arn}\n", 7)

    def _get_default_bucket_name(self) -> str:
        """
        Returns a guaranteed unique default S3 Bucket name
        """
        return "test-runner-bucket-" + str(uuid.uuid4())

    def generate_test_runner_template_string(self, image_uri: str) -> Union[dict, None]:
        """
        Renders a base jinja template to create the Test Runner Stack.

        Parameters
        ---------

        image_uri : str
            The URI of the Image to be used by the Test Runner Fargate task definition.

        Returns
        -------
        dict
            The Test Runner CloudFormation template in the form of a YAML string.

        Raises
        ------
        TestRunnerTemplateGenerationException
            If the template generation process fails
        """

        default_bucket_name = self._get_default_bucket_name()

        if self.resource_arn_list:
            statements_list = []
            for arn in self.resource_arn_list:
                statement = self._create_iam_statement_string(arn)
                if statement:
                    statements_list.append(statement)
            # Compile all the statements into a single string
            generated_statements = "".join(statements_list)
            if generated_statements:
                return (
                    self.TEST_RUNNER_TEMPLATE_STRING.replace("{{generated_statements}}", generated_statements)
                    .replace("{{image_uri}}", image_uri)
                    .replace("{{s3_bucket_name}}", default_bucket_name)
                )

        # If we have no generated statements to render, replace with empty string
        return (
            self.TEST_RUNNER_TEMPLATE_STRING.replace("{{generated_statements}}", "")
            .replace("{{image_uri}}", image_uri)
            .replace("{{s3_bucket_name}}", default_bucket_name)
        )
