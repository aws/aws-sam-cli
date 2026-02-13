"""Lambda handlers for Fn::FindInMap with DefaultValue test template.

This module provides handlers for testing Fn::FindInMap with DefaultValue option.
The handlers demonstrate:
- Existing key lookup (returns mapped value)
- Non-existent key lookup (returns DefaultValue)
- Integration with Fn::ForEach using Fn::FindInMap with DefaultValue

Each function receives configuration via environment variables set by the template.
"""

import json
import os


def handler(event, context):
    """Default Lambda handler that returns function configuration.
    
    This handler is used by functions that don't have a specific handler
    defined in the FunctionConfig mapping (uses DefaultValue).
    
    Args:
        event: Lambda event data
        context: Lambda context object
        
    Returns:
        dict: Response with function configuration information
    """
    function_name = os.environ.get("FUNCTION_NAME", "Unknown")
    log_level = os.environ.get("LOG_LEVEL", "INFO")
    test_case = os.environ.get("TEST_CASE", "unknown")
    function_description = os.environ.get("FUNCTION_DESCRIPTION", "No description")
    config_json = os.environ.get("CONFIG_JSON", "{}")
    environment_count = os.environ.get("ENVIRONMENT_COUNT", "0")
    
    return {
        "statusCode": 200,
        "body": {
            "message": f"Hello from {function_name}",
            "handler": "default_handler",
            "logLevel": log_level,
            "testCase": test_case,
            "description": function_description,
            "configJson": json.loads(config_json) if config_json else {},
            "environmentCount": int(environment_count),
            "source": "findinmap-default-template"
        }
    }


def alpha_handler(event, context):
    """Lambda handler for Alpha function.
    
    This handler is used when the FunctionConfig mapping has an entry for Alpha.
    Demonstrates Fn::FindInMap returning the mapped value when key exists.
    
    Args:
        event: Lambda event data
        context: Lambda context object
        
    Returns:
        dict: Response with Alpha function information
    """
    function_name = os.environ.get("FUNCTION_NAME", "Alpha")
    log_level = os.environ.get("LOG_LEVEL", "INFO")
    test_case = os.environ.get("TEST_CASE", "unknown")
    function_description = os.environ.get("FUNCTION_DESCRIPTION", "No description")
    
    return {
        "statusCode": 200,
        "body": {
            "message": f"Hello from {function_name}",
            "handler": "alpha_handler",
            "logLevel": log_level,
            "testCase": test_case,
            "description": function_description,
            "mappingUsed": True,
            "source": "findinmap-default-template"
        }
    }


def beta_handler(event, context):
    """Lambda handler for Beta function.
    
    This handler is used when the FunctionConfig mapping has an entry for Beta.
    Demonstrates Fn::FindInMap returning the mapped value when key exists.
    
    Args:
        event: Lambda event data
        context: Lambda context object
        
    Returns:
        dict: Response with Beta function information
    """
    function_name = os.environ.get("FUNCTION_NAME", "Beta")
    log_level = os.environ.get("LOG_LEVEL", "INFO")
    test_case = os.environ.get("TEST_CASE", "unknown")
    function_description = os.environ.get("FUNCTION_DESCRIPTION", "No description")
    
    return {
        "statusCode": 200,
        "body": {
            "message": f"Hello from {function_name}",
            "handler": "beta_handler",
            "logLevel": log_level,
            "testCase": test_case,
            "description": function_description,
            "mappingUsed": True,
            "source": "findinmap-default-template"
        }
    }


def default_handler(event, context):
    """Default Lambda handler for functions without mapping entries.
    
    This handler is used when the FunctionConfig mapping does NOT have an entry
    for the function (e.g., Gamma). Demonstrates Fn::FindInMap returning the
    DefaultValue when key does not exist.
    
    Args:
        event: Lambda event data
        context: Lambda context object
        
    Returns:
        dict: Response indicating DefaultValue was used
    """
    function_name = os.environ.get("FUNCTION_NAME", "Unknown")
    log_level = os.environ.get("LOG_LEVEL", "INFO")
    test_case = os.environ.get("TEST_CASE", "unknown")
    function_description = os.environ.get("FUNCTION_DESCRIPTION", "No description")
    
    return {
        "statusCode": 200,
        "body": {
            "message": f"Hello from {function_name}",
            "handler": "default_handler",
            "logLevel": log_level,
            "testCase": test_case,
            "description": function_description,
            "mappingUsed": False,
            "defaultValueUsed": True,
            "source": "findinmap-default-template"
        }
    }
