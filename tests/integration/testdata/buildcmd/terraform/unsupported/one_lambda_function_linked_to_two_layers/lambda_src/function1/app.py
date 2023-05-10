import json
import lib1
import lib2
import boto3


def lambda_handler(event, context):
    const_value = lib1.get_const() + lib2.get_const()
    return {
        "statusCode": 200,
        "body": f"hello world {const_value}",
    }
