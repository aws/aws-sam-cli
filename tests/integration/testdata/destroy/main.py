import json
import sys
import time


def handler(event, context):
    return {"statusCode": 200, "body": json.dumps({"hello": "world"})}
