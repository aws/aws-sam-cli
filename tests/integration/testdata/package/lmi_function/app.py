import json
import time
import os


def lambda_handler_one(event, context):
    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "hello world from function one update 1.",
        }),
    }


def lambda_handler_two(event, context):
    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "hello world from function 2",
        }),
    }