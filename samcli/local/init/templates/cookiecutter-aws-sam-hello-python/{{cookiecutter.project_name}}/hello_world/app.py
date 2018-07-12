import json

import requests


def lambda_handler(event, context):
    """Sample pure Lambda function

    Parameters
    ----------
    event: dict, required
        API Gateway Lambda Proxy Input Format

        {
            "resource": "Resource path",
            "path": "Path parameter",
            "httpMethod": "Incoming request's method name"
            "headers": {Incoming request headers}
            "queryStringParameters": {query string parameters }
            "pathParameters":  {path parameters}
            "stageVariables": {Applicable stage variables}
            "requestContext": {Request context, including authorizer-returned key-value pairs}
            "body": "A JSON string of the request payload."
            "isBase64Encoded": "A boolean flag to indicate if the applicable request payload is Base64-encode"
        }

        https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html#api-gateway-simple-proxy-for-lambda-input-format

    context: dict, required
        Lambda Context runtime methods and attributes

        {
            "aws_request_id": "Lambda request ID",
            "client_context": "Additional context",
            "function_name": "Lambda function name",
            "function_version": "Function version identifier",
            "get_remaining_time_in_millis": "Time in milliseconds before function times out",
            "identity": "Identity context from caller",
            "invoked_function_arn": "Function ARN",
            "log_group_name": "Cloudwatch Log group name",
            "log_stream_name": "Cloudwatch Log stream name",
            "memory_limit_in_mb: "Function memory"
        }

        # Lambda Python Context Object doc

    Returns
    ------
    API Gateway Lambda Proxy Output Format: dict
        'statusCode' and 'body' are required

        {
            "isBase64Encoded": true | false,
            "statusCode": httpStatusCode,
            "headers": {"headerName": "headerValue", ...},
            "body": "..."
        }

        # api-gateway-simple-proxy-for-lambda-output-format
        https: // docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html
    """

    try:
        ip = requests.get("http://checkip.amazonaws.com/")
    except requests.RequestException as e:
        error = {
            "lambda_request_id": context.aws_request_id,
            "lambda_log_group": context.log_group_name,
            "lambda_log_stream": context.log_stream_name,
            "apigw_request_id": event["requestContext"]["requestId"],
            "error_message": str(e.args),
        }

        # Send some context about this error to Lambda Logs
        print(json.dumps(error, indent=4))

        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "message": "Something went wrong :(",
                    "request_id": error["apigw_request_id"],
                }
            ),
        }

    return {
        "statusCode": 200,
        "body": json.dumps(
            {"message": "hello world", "location": ip.text.replace("\n", "")}
        ),
    }
