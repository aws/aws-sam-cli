import json

def lambda_handler(event, context):
    """Sample pure Lambda function that returns a message"""
    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Hello world!",
        }),
    }
