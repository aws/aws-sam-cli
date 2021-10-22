from aws_cdk import core as cdk
from aws_cdk import aws_lambda as _lambda, aws_apigateway as _apigw
from aws_cdk.aws_apigateway import CorsOptions, StageOptions, Integration, IntegrationType, Method, LambdaRestApiProps
from aws_cdk.aws_lambda_event_sources import ApiEventSource
from aws_cdk.core import Duration, Fn


class AwsLambdaFunctionStack(cdk.Stack):

    def __init__(self, scope: cdk.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        timeout = Duration.seconds(600)
        max_age = Duration.seconds(510)

        my_lambda_function = _lambda.Function(
            scope=self,
            id="my_lambda_function",
            function_name="MyLambdaFunction",
            timeout=timeout,
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset("./lambda_code"),
            handler="app.handler",
        )
        my_lambda_function.add_event_source(ApiEventSource("GET", "/get"))

        _lambda.Function(
            scope=self,
            id="no_api_event_function",
            function_name="NoApiEventFunction",
            timeout=timeout,
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset("./lambda_code"),
            handler="app.handler",
        )

        _lambda.Function(
            scope=self,
            id="non_serverless_function",
            function_name="MyNonServerlessLambdaFunction",
            timeout=timeout,
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset("./lambda_code"),
            handler="app.handler",
        )

        _lambda.Function(
            scope=self,
            id="base64_response",
            function_name="Base64ResponseFunction",
            timeout=timeout,
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset("./lambda_code"),
            handler="app.base64_response",
        )

        _lambda.Function(
            scope=self,
            id="base64_response_false_encoded",
            function_name="Base64ResponseFunctionWithFalseIsBase64EncodedField",
            timeout=timeout,
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset("./lambda_code"),
            handler="app.base64_with_False_isBase64Encoded_response",
        )

        _lambda.Function(
            scope=self,
            id="base64_response_true_encoded",
            function_name="Base64ResponseFunctionWithTrueBase64EncodedField",
            timeout=timeout,
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset("./lambda_code"),
            handler="app.base64_with_True_Base64Encoded_response",
        )

        _lambda.Function(
            scope=self,
            id="base_64_response_priority",
            function_name="Base64ResponseFunctionWithBase64EncodedFieldPriority",
            timeout=timeout,
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset("./lambda_code"),
            handler="app.base64_with_Base64Encoded_priority_response",
        )

        _lambda.Function(
            scope=self,
            id="echo_base_64_event_function",
            function_name="EchoBase64EventBodyFunction",
            timeout=timeout,
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset("./lambda_code"),
            handler="app.echo_base64_event_body",
        )

        echo_event_handler_function = _lambda.Function(
            scope=self,
            id="echo_event_handler_function",
            function_name="EchoEventHandlerFunction",
            timeout=timeout,
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset("./lambda_code"),
            handler="app.echo_event_handler",
        )
        echo_event_handler_function.add_event_source(ApiEventSource("GET", "/{proxy+}"))

        cors_options = CorsOptions(
            allow_origins=['*'],
            allow_methods=['GET'],
            allow_headers=['origin', 'x-requested-with'],
            allow_credentials=True,
            max_age=max_age
        )

        api = _apigw.RestApi(
            self,
            "api",
            binary_media_types=["image/gif"],
            default_cors_preflight_options=cors_options
        )

        function_with_no_api_event_integration = Integration(
            type=IntegrationType.AWS_PROXY,
            integration_http_method="POST",
            uri=Fn.sub("arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${NoApiEventFunction.Arn}/invocations"),
        )
        function_with_no_api_event = api.root.add_resource("functionwithnoapievent", default_integration=function_with_no_api_event_integration)
        function_with_no_api_event.add_method("GET")

        any_and_all_integration = Integration(
            type=IntegrationType.AWS_PROXY,
            integration_http_method="POST",
            uri=Fn.sub("arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${MyLambdaFunction.Arn}/invocations"),
        )
        any_and_all_integration = api.root.add_resource("anyandall", default_integration=any_and_all_integration)
        any_and_all_integration.add_method("ANY")

        non_serverless_function = Integration(
            type=IntegrationType.AWS_PROXY,
            integration_http_method="POST",
            uri=Fn.sub(
                "arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${MyNonServerlessLambdaFunction.Arn}/invocations"),
        )
        non_serverless_function = api.root.add_resource("nonserverlessfunction", default_integration=non_serverless_function)
        non_serverless_function.add_method("GET")

        no_function_found = Integration(
            type=IntegrationType.AWS_PROXY,
            integration_http_method="POST",
            uri=Fn.sub(
                "arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${WhatFunction.Arn}/invocations"),
        )
        no_function_found = api.root.add_resource("nofunctionfound", default_integration=no_function_found)
        no_function_found.add_method("GET")

        base64_response = Integration(
            type=IntegrationType.AWS_PROXY,
            integration_http_method="POST",
            uri=Fn.sub(
                "arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${Base64ResponseFunction.Arn}/invocations"),
        )
        base64_response = api.root.add_resource("base64response", default_integration=base64_response)
        base64_response.add_method("GET")

        non_decode_base64_response = Integration(
            type=IntegrationType.AWS_PROXY,
            integration_http_method="POST",
            uri=Fn.sub(
                "arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${Base64ResponseFunctionWithFalseIsBase64EncodedField.Arn}/invocations"),
        )
        non_decode_base64_response = api.root.add_resource("nondecodedbase64response", default_integration=non_decode_base64_response)
        non_decode_base64_response.add_method("GET")

        decode_base_64_response = Integration(
            type=IntegrationType.AWS_PROXY,
            integration_http_method="POST",
            uri=Fn.sub(
                "arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${Base64ResponseFunctionWithTrueBase64EncodedField.Arn}/invocations"),
        )
        decode_base_64_response = api.root.add_resource("decodedbase64responsebas64encoded", default_integration=decode_base_64_response)
        decode_base_64_response.add_method("GET")

        decode_base64_priority = Integration(
            type=IntegrationType.AWS_PROXY,
            integration_http_method="POST",
            uri=Fn.sub(
                "arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${Base64ResponseFunctionWithBase64EncodedFieldPriority.Arn}/invocations"),
        )
        decode_base64_priority = api.root.add_resource("decodedbase64responsebas64encodedpriority", default_integration=decode_base64_priority)
        decode_base64_priority.add_method("GET")

        echo_base64_event_body = Integration(
            type=IntegrationType.AWS_PROXY,
            integration_http_method="POST",
            uri=Fn.sub(
                "arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${EchoBase64EventBodyFunction.Arn}/invocations"),
        )
        echo_base64_event_body = api.root.add_resource("echobase64eventbody", default_integration=echo_base64_event_body)
        echo_base64_event_body.add_method("POST")

        echo_event_body = Integration(
            type=IntegrationType.AWS_PROXY,
            integration_http_method="POST",
            uri=Fn.sub(
                "arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${EchoEventHandlerFunction.Arn}/invocations"),
        )
        echo_event_body = api.root.add_resource("echoeventbody", default_integration=echo_event_body)
        echo_event_body.add_method("POST")
