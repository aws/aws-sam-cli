import json
import lib
import boto3

def lambda_handler(event, context):
    const_value = lib.get_const()
    return {
        "statusCode": 200,
        "body": f"hello world {const_value}",
    }
