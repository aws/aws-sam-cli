import json
def lambda_handler(event, context):
    print("list books function start")

    books = []

    return {
        "statusCode": 200,
        "body": json.dumps(books),
    }
