import sys
import site

sys.path.insert(0, "/opt")
site.addsitedir("/opt")


def handler(event, context):
    return "hello"


def custom_layer_handler(event, context):
    from my_layer.simple_python import layer_ping

    return layer_ping()


def one_layer_hanlder(event, context):
    from simple_python_module.simple_python import which_layer

    return which_layer()
