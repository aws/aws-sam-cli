from aws_cdk import core as cdk

# For consistency with other languages, `cdk` is the preferred import name for
# the CDK's core module.  The following line also imports it as `core` for use
# with examples from the CDK Developer's Guide, which are in the process of
# being updated to use `cdk`.  You may delete this import if you don't need it.
from aws_cdk import aws_lambda as _lambda, aws_apigateway as _apigw
from aws_cdk.aws_lambda_event_sources import ApiEventSource
from aws_cdk.core import Duration

DEFAULT_TIMEOUT = 5


class AwsLambdaFunctionStack(cdk.Stack):

    def __init__(self, scope: cdk.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        timeout = Duration.seconds(600)

        hello_world_function = _lambda.Function(
            scope=self,
            id="helloworld-function",
            function_name="HelloWorldFunction",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset("./lambda_code"),
            handler="app.handler",
        )
        hello_world_function.add_event_source(ApiEventSource("GET", "/proxypath/{proxy+}"))
        hello_world_function.add_event_source(ApiEventSource("POST", "/id"))
        hello_world_function.add_event_source(ApiEventSource("ANY", "/anyandall"))

        echo_event_function = _lambda.Function(
            scope=self,
            id="echo_event_function",
            function_name="EchoEventFunction",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset("./lambda_code"),
            handler="app.echo_event_handler",
        )
        echo_event_function.add_event_source(ApiEventSource("GET", "/id/{id}/user/{user}"))
        echo_event_function.add_event_source(ApiEventSource("GET", "/id/{id}"))
        echo_event_function.add_event_source(ApiEventSource("POST", "/echoeventbody"))

        echo_event_function_2 = _lambda.Function(
            scope=self,
            id="echo_event_function_2",
            function_name="EchoEventFunction2",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset("./lambda_code"),
            handler="app.echo_event_handler_2",
        )
        echo_event_function_2.add_event_source(ApiEventSource("GET", "/echoeventbody"))

        echo_integer_body_function = _lambda.Function(
            scope=self,
            id="echo_integer_body_function",
            function_name="EchoIntegerBodyFunction",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset("./lambda_code"),
            handler="app.echo_integer_body",
        )
        echo_integer_body_function.add_event_source(ApiEventSource("GET", "/echo_integer_body"))

        content_type_setter_function = _lambda.Function(
            scope=self,
            id="content_type_setter_function",
            function_name="ContentTypeSetterFunction",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset("./lambda_code"),
            handler="app.content_type_setter_handler",
        )
        content_type_setter_function.add_event_source(ApiEventSource("GET", "/getcontenttype"))

        only_set_status_code_function = _lambda.Function(
            scope=self,
            id="only_set_status_code_function",
            function_name="OnlySetStatusCodeFunction",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset("./lambda_code"),
            handler="app.only_set_status_code_handler",
        )
        only_set_status_code_function.add_event_source(ApiEventSource("GET", "/onlysetstatuscode"))

        only_set_body_function = _lambda.Function(
            scope=self,
            id="only_set_body_function",
            function_name="OnlySetBodyFunction",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset("./lambda_code"),
            handler="app.only_set_body_handler",
        )
        only_set_body_function.add_event_source(ApiEventSource("GET", "/onlysetbody"))

        string_status_code_function = _lambda.Function(
            scope=self,
            id="string_status_code_function",
            function_name="StringStatusCodeFunction",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset("./lambda_code"),
            handler="app.string_status_code_handler",
        )
        string_status_code_function.add_event_source(ApiEventSource("GET", "/stringstatuscode"))

        sleep_10_sec_function = _lambda.Function(
            scope=self,
            id="sleep_10_sec_function",
            function_name="SleepFunction0",
            timeout=timeout,
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset("./lambda_code"),
            handler="app.sleep_10_sec_handler",
        )
        sleep_10_sec_function.add_event_source(ApiEventSource("GET", "/sleepfortenseconds/function0"))

        sleep_function_1 = _lambda.Function(
            scope=self,
            id="sleep_function_1",
            function_name="SleepFunction1",
            timeout=timeout,
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset("./lambda_code"),
            handler="app.sleep_10_sec_handler",
        )
        sleep_function_1.add_event_source(ApiEventSource("GET", "/sleepfortenseconds/function1"))

        write_to_stderr_function = _lambda.Function(
            scope=self,
            id="write_to_stderr",
            function_name="WriteToStderrFunction",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset("./lambda_code"),
            handler="app.write_to_stderr",
        )
        write_to_stderr_function.add_event_source(ApiEventSource("GET", "/writetostderr"))

        write_to_stdout_function = _lambda.Function(
            scope=self,
            id="write_to_stdout_function",
            function_name="WriteToStdoutFunction",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset("./lambda_code"),
            handler="app.write_to_stdout",
        )
        write_to_stdout_function.add_event_source(ApiEventSource("GET", "/writetostdout"))

        invalid_response_returned_function = _lambda.Function(
            scope=self,
            id="invalid_response_returned_function",
            function_name="InvalidResponseFromLambdaFunction",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset("./lambda_code"),
            handler="app.invalid_response_returned",
        )
        invalid_response_returned_function.add_event_source(ApiEventSource("GET", "/invalidresponsereturned"))

        invalid_hash_response_function = _lambda.Function(
            scope=self,
            id="invalid_hash_response_function",
            function_name="InvalidResponseHashFromLambdaFunction",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset("./lambda_code"),
            handler="app.invalid_hash_response",
        )
        invalid_hash_response_function.add_event_source(ApiEventSource("GET", "/invalidresponsehash"))

        base64_response_function = _lambda.Function(
            scope=self,
            id="base64_response_function",
            function_name="Base64ResponseFunction",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset("./lambda_code"),
            handler="app.base64_response",
        )
        base64_response_function.add_event_source(ApiEventSource("GET", "/base64response"))

        echo_base64_event_body_function = _lambda.Function(
            scope=self,
            id="echo_base64_event_body_function",
            function_name="EchoBase64EventBodyFunction",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset("./lambda_code"),
            handler="app.echo_base64_event_body",
        )
        echo_base64_event_body_function.add_event_source(ApiEventSource("GET", "/echobase64eventbody"))

        multiple_headers_function = _lambda.Function(
            scope=self,
            id="multiple_headers_function",
            function_name="MultipleHeadersResponseFunction",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset("./lambda_code"),
            handler="app.multiple_headers",
        )
        multiple_headers_function.add_event_source(ApiEventSource("GET", "/multipleheaders"))

        multiple_headers_overrides_headers_function = _lambda.Function(
            scope=self,
            id="multiple_headers_overrides_headers_function",
            function_name="MultipleHeadersOverridesHeadersResponseFunction",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset("./lambda_code"),
            handler="app.multiple_headers_overrides_headers",
        )
        multiple_headers_overrides_headers_function.add_event_source(ApiEventSource("GET", "/multipleheadersoverridesheaders"))

