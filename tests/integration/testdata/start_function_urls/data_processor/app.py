import json

def lambda_handler(event, context):
    """
    Lambda function for data processing with Function URL
    """
    
    # Extract HTTP method and body
    http_method = event.get('requestContext', {}).get('http', {}).get('method', 'UNKNOWN')
    body = event.get('body', '')
    
    # Parse body if it's JSON
    data = None
    if body:
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            data = {'raw': body}
    
    # Process based on method
    if http_method == 'POST':
        response_message = 'Data received for processing'
    elif http_method == 'PUT':
        response_message = 'Data updated'
    elif http_method == 'DELETE':
        response_message = 'Data deleted'
    else:
        response_message = f'Method {http_method} received'
    
    response_body = {
        'message': response_message,
        'method': http_method,
        'function': 'DataProcessorFunction',
        'data_received': data,
        'event_version': event.get('version', 'unknown')
    }
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'X-Function-Name': 'DataProcessorFunction',
            'Access-Control-Allow-Origin': 'https://example.com'
        },
        'body': json.dumps(response_body)
    }
