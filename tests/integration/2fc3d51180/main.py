
import json

def handler(event, context):
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Hello from CDK Function URL!',
            'source': 'cdk'
        })
    }
