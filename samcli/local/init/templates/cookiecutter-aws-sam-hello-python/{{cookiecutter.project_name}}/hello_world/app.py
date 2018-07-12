import json

import requests


def lambda_handler(event, context):
    """Sample pure Lambda function

    Arguments:
        event LambdaEvent -- Lambda Event received from Invoke API
        context LambdaContext -- Lambda Context runtime methods and attributes

    Returns:
        dict -- {'statusCode': int, 'body': dict}
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
