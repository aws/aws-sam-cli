import json

def lambda_handler(event, context):
    """
    Lambda function with AWS_IAM authentication
    """
    
    # This would normally have IAM authentication in production
    # For local testing, we're simulating an authenticated endpoint
    
    # Extract authorization header
    headers = event.get('headers', {})
    auth_header = headers.get('authorization', headers.get('Authorization', ''))
    
    response_body = {
        'message': 'This is a protected endpoint',
        'function': 'AuthenticatedFunction',
        'auth_header_present': bool(auth_header),
        'event_version': event.get('version', 'unknown')
    }
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'X-Function-Name': 'AuthenticatedFunction'
        },
        'body': json.dumps(response_body)
    }
