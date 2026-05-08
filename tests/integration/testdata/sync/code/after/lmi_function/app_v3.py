"""
Lambda functions for LMI integration tests - Version 3 (Final).
"""
import json
import os


def env_var_handler(event, context):
    """
    Returns environment variables, particularly AWS_LAMBDA_MAX_CONCURRENCY.
    Used for testing capacity provider configuration and version publishing.
    
    This is version 3 - the final version.
    """
    max_concurrency = os.environ.get('AWS_LAMBDA_MAX_CONCURRENCY', 'not set')
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Hello from LMI function - UPDATE 3',
            'max_concurrency': max_concurrency,
            'version': 'v3'
        })
    }
