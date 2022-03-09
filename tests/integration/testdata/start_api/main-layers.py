import json
import sys
import site

sys.path.insert(0, "/opt")
site.addsitedir("/opt")

def custom_layer_handler(event, context):
    from simple_python_module.simple_python import which_layer
    return {"body": json.dumps(which_layer())}
