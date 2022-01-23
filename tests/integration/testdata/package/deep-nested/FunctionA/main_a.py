import json


def handler(event, context):
    """
    FunctionA in root template
    """
    return {"statusCode": 200, "body": json.dumps({"hello": "world"})}
