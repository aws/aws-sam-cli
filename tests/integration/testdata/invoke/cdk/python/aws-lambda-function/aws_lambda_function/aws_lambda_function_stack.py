from aws_cdk import core as cdk

# For consistency with other languages, `cdk` is the preferred import name for
# the CDK's core module.  The following line also imports it as `core` for use
# with examples from the CDK Developer's Guide, which are in the process of
# being updated to use `cdk`.  You may delete this import if you don't need it.
from aws_cdk import core, aws_lambda as _lambda, aws_iam as _iam

DEFAULT_TIMEOUT = 5

class AwsLambdaFunctionStack(cdk.Stack):

    def __init__(self, scope: cdk.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        _lambda.Function(
            scope=self,
            id="helloworld-serverless-function",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset("./lambda_code"),
            handler="app.handler",
        )

        _lambda.Function(
            scope=self,
            id="timeout-function",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset("./lambda_code"),
            handler="app.timeout_handler",
            timeout=core.Duration.seconds(DEFAULT_TIMEOUT)
        )

        _lambda.Function(
            scope=self,
            id="custom-env-vars-function",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset("./lambda_code"),
            handler="app.custom_env_var_echo_handler",
            environment={"CustomEnvVar": "MyVar"}
        )

        _lambda.Function(
            scope=self,
            id="write-to-stdout-function",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset("./lambda_code"),
            handler="app.write_to_stdout",
        )

        _lambda.Function(
            scope=self,
            id="write-to-stderr-function",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset("./lambda_code"),
            handler="app.write_to_stderr",
        )

        _lambda.Function(
            scope=self,
            id="echo-event-function",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset("./lambda_code"),
            handler="app.echo_event",
        )

        _lambda.Function(
            scope=self,
            id="echo-env-with-parameters",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset("./lambda_code"),
            handler="app.env_var_echo_handler",
            environment={
                         "TimeOut": str(DEFAULT_TIMEOUT),
                         "MyRuntimeVersion": "",
                         "EmptyDefaultParameter": ""}
        )
        
        core.CfnParameter(
            scope=self,
            id="custom-parameter",
            type="String",
            description="A custom parameter",
            default="Sample",
        )

