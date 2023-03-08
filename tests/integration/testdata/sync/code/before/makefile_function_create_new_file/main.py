import json
import requests

import mylayer


def handler(event, context):
    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": f"function requests version: {requests.__version__}, layer six version: {mylayer.get_six_version()}",
            }
        ),
    }
