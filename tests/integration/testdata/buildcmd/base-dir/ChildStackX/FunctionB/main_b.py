import json


def handler(event, context):
    """
    FunctionB in child template
    """
    return {"statusCode": 200, "body": json.dumps({"hello": "b"})}
