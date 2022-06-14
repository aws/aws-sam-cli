import json
import numpy as np

def lambda_handler(event, context):

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "hello mars",
            "extra_message": np.array([1, 2, 3, 4, 5, 6]).tolist()  # checking external library call will succeed
        }),
    }
