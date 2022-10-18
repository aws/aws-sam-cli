import json
import boto3
import os


def handler(event, context):
    print("Function starts")
    return {
        "statusCode": 200,
        "body": json.dumps([]),
    }