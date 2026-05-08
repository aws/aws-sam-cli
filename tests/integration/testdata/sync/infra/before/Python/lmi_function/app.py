"""
Lambda functions for LMI integration tests.
"""
import json
import os


def env_var_handler(event, context):
    """
    Returns environment variables, particularly AWS_LAMBDA_MAX_CONCURRENCY.
    Used for testing capacity provider configuration and version publishing.
    """
    max_concurrency = os.environ.get('AWS_LAMBDA_MAX_CONCURRENCY', 'not set')
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Hello from LMI function',
            'max_concurrency': max_concurrency,
        })
    }
