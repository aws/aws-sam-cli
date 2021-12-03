import json
from layer_method import layer_method

import requests


def lambda_handler(event, context):
    """Sample pure Lambda function that returns a message and a location"""

    try:
        ip = requests.get("http://checkip.amazonaws.com/")
    except requests.RequestException as e:
        # Send some context about this error to Lambda Logs
        print(e)

        raise e

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": f"{layer_method()+2}",
            "location": ip.text.replace("\n", "")
        }),
    }
