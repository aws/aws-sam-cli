"""
Lambda function handler for API Gateway events
"""
import json


def lambda_handler(event, context):
    """
    Lambda function handler for API Gateway REST API
    
    This handler processes API Gateway v1.0 (REST API) events
    """
    
    # Log the incoming event
    print(f"Received event: {json.dumps(event)}")
    
    # Extract information from the API Gateway event
    http_method = event.get('httpMethod', 'GET')
    path = event.get('path', '/')
    query_params = event.get('queryStringParameters', {})
    headers = event.get('headers', {})
    body = event.get('body', None)
    path_params = event.get('pathParameters', {})
    
    # Parse body if it's JSON
    request_body = None
    if body:
        try:
            request_body = json.loads(body)
        except json.JSONDecodeError:
            request_body = body
    
    # Build response based on the request
    response_body = {
        "message": "Hello from API Gateway!",
        "method": http_method,
        "path": path,
        "queryParameters": query_params,
        "pathParameters": path_params,
        "headers": {
            "User-Agent": headers.get('User-Agent', 'Unknown'),
            "Host": headers.get('Host', 'Unknown')
        },
        "timestamp": context.aws_request_id if context else "local-test"
    }
    
    # Add request body to response if present
    if request_body:
        response_body["requestBody"] = request_body
    
    # Return API Gateway response format
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "X-Custom-Header": "API Gateway Test"
        },
        "body": json.dumps(response_body)
    }
