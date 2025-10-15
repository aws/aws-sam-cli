import json

def lambda_handler(event, context):
    """
    Lambda function that handles Function URL requests
    Expects v2.0 payload format
    """
    
    # Log the incoming event for debugging
    print(f"Received event: {json.dumps(event)}")
    
    # Extract information from v2.0 format
    http_method = event.get('requestContext', {}).get('http', {}).get('method', 'UNKNOWN')
    path = event.get('rawPath', '/')
    query_params = event.get('queryStringParameters', {})
    headers = event.get('headers', {})
    
    # Get name from query parameters or use default
    name = query_params.get('name', 'World') if query_params else 'World'
    
    # Build response
    response_body = {
        'message': f'Hello {name}!',
        'method': http_method,
        'path': path,
        'function': 'HelloWorldFunction',
        'event_version': event.get('version', 'unknown')
    }
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'X-Function-Name': 'HelloWorldFunction'
        },
        'body': json.dumps(response_body)
    }
