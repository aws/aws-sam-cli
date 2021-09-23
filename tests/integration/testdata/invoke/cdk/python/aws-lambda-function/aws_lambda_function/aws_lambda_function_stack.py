from aws_cdk import core as cdk

# For consistency with other languages, `cdk` is the preferred import name for
# the CDK's core module.  The following line also imports it as `core` for use
# with examples from the CDK Developer's Guide, which are in the process of
# being updated to use `cdk`.  You may delete this import if you don't need it.
from aws_cdk import core, aws_lambda_python, aws_lambda as _lambda, aws_apigateway as _apigw
from aws_cdk.aws_lambda_event_sources import ApiEventSource
from aws_cdk.core import CfnParameter, Fn

DEFAULT_TIMEOUT = 5


class AwsLambdaFunctionStack(cdk.Stack):

    def __init__(self, scope: cdk.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        CfnParameter(self, "ModeEnvVariable", type="String")

        _lambda.Function(
            scope=self,
            id="helloworld-function",
            function_name="HelloWorldFunction",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset("./lambda_code"),
            handler="app.hello_world_handler",
            environment={"MODE": Fn.ref("ModeEnvVariable")},
        )

        _lambda.Function(
            scope=self,
            id="helloworld-serverless-function",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset("./lambda_code"),
            handler="app.handler",
            environment={"MODE": Fn.ref("ModeEnvVariable")}
        )

        _lambda.Function(
            scope=self,
            id="timeout-function",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset("./lambda_code"),
            handler="app.sleeptime_handler",
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
            function_name="CDKEchoEventFunction",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset("./lambda_code"),
            handler="app.echo_event",
        )

        my_runtime_version_parameter = core.CfnParameter(
            scope=self,
            id="MyRuntimeVersion",
            type="String",
            description="A custom parameter",
            default="",
        )

        empty_default_parameter = core.CfnParameter(
            scope=self,
            id="EmptyDefaultParameter",
            type="String",
            description="A custom parameter",
            default="",
        )

        _lambda.Function(
            scope=self,
            id="echo-env-with-parameters",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset("./lambda_code"),
            environment={
                "MyRuntimeVersion": my_runtime_version_parameter.value_as_string,
                "EmptyDefaultParameter": empty_default_parameter.value_as_string
            },
            handler="app.parameter_echo_handler"
        )

        _lambda.DockerImageFunction(
            scope=self,
            id="lambda-docker-function",
            function_name="DockerImageFunction",

            code=_lambda.DockerImageCode.from_image_asset(
                "./docker_lambda_code",
                cmd=['app.get'],
                entrypoint=["/lambda-entrypoint.sh"],
                file='Dockerfile',
            ),
        )

        aws_lambda_python.PythonFunction(
            scope=self,
            id="python-function-construct",
            runtime=_lambda.Runtime.PYTHON_3_8,
            index="app.py",
            entry="./lambda_code",
            handler="handler"
        )
