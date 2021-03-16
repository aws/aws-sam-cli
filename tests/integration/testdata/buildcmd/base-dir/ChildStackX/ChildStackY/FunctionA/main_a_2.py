import json


def handler(event, context):
    """
    FunctionA in leaf template
    """
    return {"statusCode": 200, "body": json.dumps({"hello": "a2"})}
