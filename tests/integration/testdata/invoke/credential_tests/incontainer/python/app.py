import boto3
import json


def lambda_handler(event, context):
    client = boto3.client('sts')
    response = client.get_caller_identity()

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "hello world",
            "account": response.get('Account')
        }),
    }
