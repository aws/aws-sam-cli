# Common utilities layer
# This file is part of the Common layer for language-extensions-dynamic-contenturi test

def get_common_config():
    """Return common configuration."""
    return {
        "layer": "Common",
        "version": "1.0.0"
    }

def format_response(data):
    """Format a standard response."""
    return {
        "statusCode": 200,
        "body": data
    }
