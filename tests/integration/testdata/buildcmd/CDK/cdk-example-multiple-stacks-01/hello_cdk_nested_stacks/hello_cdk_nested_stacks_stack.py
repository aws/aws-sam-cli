from aws_cdk import core as cdk

# For consistency with other languages, `cdk` is the preferred import name for
# the CDK's core module.  The following line also imports it as `core` for use
# with examples from the CDK Developer's Guide, which are in the process of
# being updated to use `cdk`.  You may delete this import if you don't need it.
from aws_cdk import (
    aws_lambda as _lambda,
    aws_sam as sam,
    aws_iam as _iam,
    aws_cloudformation as cfn,
    core
)


class RootStack(core.Stack):
    def __init__(self, scope: cdk.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        cdk_lambda = _lambda.DockerImageFunction(
            scope=self,
            id="container-function",
            code=_lambda.DockerImageCode.from_image_asset(
                "./docker_lambda_code",
                cmd=['app.get'],
                entrypoint=["/lambda-entrypoint.sh"],
            ),
        )

        remote_nested_stack = cfn.CfnStack(
            scope=self,
            id="remote-nested-stack",
            template_url="s3://bucket/key",
        )
    

class HelloCdkNestedStacksStack(cfn.NestedStack):

    def __init__(self, scope: cdk.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # The code that defines your stack goes here
        self.lambda_role =  _iam.Role(
            scope=self,
            id="cdk-lambda-role",
            assumed_by=_iam.ServicePrincipal("lambda.amazonaws.com"),
            role_name="cdk-lambda-role-nested",
            managed_policies=[
                _iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ]
        )

        cdk_lambda = _lambda.Function(
            scope=self,
            id="cdk-wing-test-lambda",
            runtime=_lambda.Runtime.PYTHON_3_7,
            function_name="cdk-wing-test-lambda-nested",
            description="Lambda function deployed using AWS CDK Python",
            code=_lambda.Code.from_asset("./stack1_lambda_code"),
            handler="app.lambda_handler",
            role=self.lambda_role,
        )

class NestedNestedStack(cfn.NestedStack):
    def __init__(self, scope: cdk.Construct, construct_id: str, lambda_role: _iam.Role, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        cdk_lambda = _lambda.Function(
            scope=self,
            id="cdk-wing-test-lambda",
            runtime=_lambda.Runtime.PYTHON_3_7,
            function_name="cdk-wing-test-lambda-stack3",
            description="Lambda function deployed using AWS CDK Python",
            code=_lambda.Code.from_asset("./stack3_lambda_code"),
            handler="app.lambda_handler",
            role=lambda_role,
        )



class Stack2(core.Stack):

    def __init__(self, scope: cdk.Construct, construct_id: str, lambda_role: _iam.Role, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        cdk_lambda = _lambda.Function(
            scope=self,
            id="cdk-wing-test-lambda",
            runtime=_lambda.Runtime.PYTHON_3_7,
            function_name="cdk-wing-test-lambda-stack2",
            description="Lambda function deployed using AWS CDK Python",
            code=_lambda.Code.from_asset("./stack2_lambda_code"),
            handler="app.lambda_handler",
            role=lambda_role,
        )
