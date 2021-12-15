import os
import sys
import time


def hello_world_handler(event, context):
    return "Hello world!"


def handler(event, context):
    print ("value1 = " + event["key1"])
    print ("value2 = " + event["key2"])
    print ("value3 = " + event["key3"])
    print("value1 = " + event["key1"])
    print("value2 = " + event["key2"])
    print("value3 = " + event["key3"])

    sys.stdout.write("Docker Lambda is writing to stderr")

    return "Hello world"


def timeout_handler(event, context):
    time.sleep(10)
    return "Slept for 10s"


def custom_env_var_echo_handler(event, context):
    return os.environ.get("CustomEnvVar")


def write_to_stdout(event, context):
    sys.stdout.write("Docker Lambda is writing to stdout")
    return "wrote to stdout"


def write_to_stderr(event, context):
    sys.stderr.write("Docker Lambda is writing to stderr")
    return "wrote to stderr"


def echo_event(event, context):
    return event


def parameter_echo_handler(event, context):
    return dict(os.environ)

