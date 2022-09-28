import json
import boto3
import os 

#import ptvsd

#ptvsd.enable_attach(address=('0.0.0.0', 9999), redirect_output=True)
#ptvsd.wait_for_attach()

def lambda_handler(event, context):
    print("list books function start")

    # books_table = os.environ['books_table_id']
    # dynamodb = boto3.client('dynamodb')
    # paginator = dynamodb.get_paginator("scan")
    
    books = []
    # for page in paginator.paginate(TableName=books_table):
    #     for item in page["Items"]:
    #         print(f"Debugging Message - dynamodb scan output {item}")
    #         print(f"Debugging Message - dynamodb scan output {item}")
            
    #         books.append({
    #             "book_id": item.get("id").get("S"),
    #             "book_title": item.get("title").get("S"),
    #             "book_language": item.get("language").get("S"),
    #         })


    return {
        "statusCode": 200,
        "body": json.dumps(books),
    }
