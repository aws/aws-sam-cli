import json
from root_layer import layer_method

def lambda_handler(event, context):
    """Sample pure Lambda function that returns a message and a location"""

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": f"{layer_method()+5}"
        }),
    }