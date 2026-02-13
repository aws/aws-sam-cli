# Utils layer
# This file is part of the Utils layer for language-extensions-dynamic-contenturi test

import json

def to_json(data):
    """Convert data to JSON string."""
    return json.dumps(data)

def from_json(json_str):
    """Parse JSON string to data."""
    return json.loads(json_str)

def get_utils_info():
    """Return utils layer info."""
    return {
        "layer": "Utils",
        "version": "1.0.0"
    }
