from aws_cdk import core as cdk

# For consistency with other languages, `cdk` is the preferred import name for
# the CDK's core module.  The following line also imports it as `core` for use
# with examples from the CDK Developer's Guide, which are in the process of
# being updated to use `cdk`.  You may delete this import if you don't need it.
from aws_cdk import core, aws_lambda as _lambda, aws_iam as _iam


class AwsLambdaFunctionStack(cdk.Stack):

    def __init__(self, scope: cdk.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # The code that defines your stack goes here
        _lambda.Function(
            scope=self,
            id="lambda-function",
            runtime=_lambda.Runtime.PYTHON_3_7,
            code=_lambda.Code.from_asset("./lambda_code"),
            handler="app.handler",
        )
        
        core.CfnParameter(
            scope=self,
            id="custom-parameter",
            type="String",
            description="A custom parameter",
            default="Sample",
        )

