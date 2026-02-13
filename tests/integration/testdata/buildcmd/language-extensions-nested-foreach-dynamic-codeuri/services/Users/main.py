"""Users service handler."""


def handler(event, context):
    return {"statusCode": 200, "body": {"service": "Users"}}
