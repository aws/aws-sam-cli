import json
from layer import layer_method

# import numpy as np
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
            "message": f"{layer_method()+1}",
            "location": ip.text.replace("\n", "")
            # "extra_message": np.array([1, 2, 3, 4, 5, 6]).tolist() # checking external library call will succeed
        }),
    }