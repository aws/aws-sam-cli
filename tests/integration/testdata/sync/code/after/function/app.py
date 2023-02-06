import json
from layer_method import layer_method

import numpy as np


def lambda_handler(event, context):
    """Sample pure Lambda function that returns a message and a location"""

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": f"{layer_method()+2}",
            "message_from_layer": f"{layer_method()}",
            "extra_message": np.array([1, 2, 3, 4, 5, 6]).tolist() # checking external library call will succeed
        }),
    }
