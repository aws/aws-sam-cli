""" Pipeline stage"""
from .resource import Resource, S3Bucket


class Stage:
    """
    Represents a pipeline stage

    Attributes
    ----------
    name: str
        The name of the stage
    aws_profile: str
        The named AWS profile(in user's machine) of the AWS account to deploy this stage to.
    aws_region: str
        The AWS region to deploy this stage to.
    stack_name: str
        The stack-name to be used for deploying the application's CFN template to this stage.
    deployer_role: Resource
        The IAM role assumed by the pipeline's deployer IAM user to get access to the AWS account and executes the
        CloudFormation stack.
    cfn_deployment_role: Resource
        The IAM role assumed by the CloudFormation service to executes the CloudFormation stack.
    artifacts_bucket: S3Bucket
        The S3 bucket to hold the SAM build artifacts of the application's CFN template.

    Methods:
    did_user_provide_all_required_resources() -> bool:
        checks if all of the stage requires resources(deployer_role, cfn_deployment_role, artifacts_bucket) are provided
        by the user.
    deployer_role_permissions(deployer_arn):
        returns a string of the permissions(IAM policies) required for the deployer_role to operate as expected.
    cfn_deployment_role_permissions():
        returns a string of the permissions(IAM policies) required for the cfn_deployment_role to operate as expected.
    artifacts_bucket_permissions():
        returns a string of the permissions(IAM policies) required for the artifacts_bucket to operate as expected.

    """

    def __init__(
        self,
        name: str,
        aws_profile: str,
        aws_region: str,
        stack_name: str,
        deployer_role_arn: str,
        cfn_deployment_role_arn: str,
        artifacts_bucket_arn: str,
    ) -> None:
        self.name: str = name
        self.aws_profile: str = aws_profile
        self.aws_region: str = aws_region
        self.stack_name: str = stack_name
        self.deployer_role: Resource = Resource(arn=deployer_role_arn)
        self.cfn_deployment_role: Resource = Resource(arn=cfn_deployment_role_arn)
        self.artifacts_bucket: S3Bucket = S3Bucket(arn=artifacts_bucket_arn)

    def did_user_provide_all_required_resources(self) -> bool:
        return (
            self.artifacts_bucket.is_user_provided
            and self.deployer_role.is_user_provided
            and self.cfn_deployment_role.is_user_provided
        )

    def deployer_role_permissions(self, deployer_arn: str) -> str:
        permissions: str = f"""
AssumeRolePolicyDocument:
  Version: 2012-10-17
  Statement:
    - Effect: Allow
      Principal:
        AWS: {deployer_arn}
      Action:
        - 'sts:AssumeRole'
Policies:
  - PolicyName: AccessRolePolicy
    PolicyDocument:
      Version: 2012-10-17
      Statement:
        - Effect: Allow
          Action:
            - 'iam:PassRole'
          Resource:
            - "{self.cfn_deployment_role.arn}"
        - Effect: Allow
          Action:
            - "cloudformation:CreateChangeSet"
            - "cloudformation:DescribeChangeSet"
            - "cloudformation:ExecuteChangeSet"
            - "cloudformation:DescribeStackEvents"
            - "cloudformation:DescribeStacks"
            - "cloudformation:GetTemplateSummary"
            - "cloudformation:DescribeStackResource"
          Resource: '*'
        - Effect: Allow
          Action:
            - 's3:GetObject*'
            - 's3:PutObject*'
            - 's3:GetBucket*'
            - 's3:List*'
          Resource:
            - {self.artifacts_bucket.arn}
            - {self.artifacts_bucket.arn}/*
        """
        if not self.artifacts_bucket.is_user_provided:
            permissions += f"""
        - Effect: Allow
          Action:
            - "kms:Decrypt"
            - "kms:DescribeKey"
          Resource:
            - {self.artifacts_bucket.kms_key_arn}
            """
        return permissions

    def cfn_deployment_role_permissions(self) -> str:
        permissions: str = """
AssumeRolePolicyDocument:
  Version: 2012-10-17
  Statement:
    - Effect: Allow
      Principal:
        Service: cloudformation.amazonaws.com
      Action:
        - 'sts:AssumeRole'
Policies:
  - PolicyName: GrantCloudFormationFullAccess
    PolicyDocument:
      Version: 2012-10-17
      Statement:
        - Effect: Allow
          Action: '*'
          Resource: '*'
        """
        return permissions

    def artifacts_bucket_permissions(self) -> str:
        permissions: str = f"""
PolicyDocument:
  Statement:
    - Effect: "Allow"
      Action:
        - 's3:GetObject*'
        - 's3:PutObject*'
        - 's3:GetBucket*'
        - 's3:List*'
      Resource:
        - {self.artifacts_bucket.arn}
        - {self.artifacts_bucket.arn}/*
      Principal:
        AWS:
          - {self.deployer_role.arn}
          - {self.cfn_deployment_role.arn}
        """
        return permissions
