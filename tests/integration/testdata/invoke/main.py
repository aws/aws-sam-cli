import time
import os
import sys
import subprocess

print ("Loading function")


def handler(event, context):
    print ("value1 = " + event["key1"])
    print ("value2 = " + event["key2"])
    print ("value3 = " + event["key3"])

    sys.stdout.write("Docker Lambda is writing to stderr")

    return "Hello world"

def intrinsics_handler(event, context):
    return os.environ.get("ApplicationId")

def sleep_handler(event, context):
    time.sleep(10)
    return "Slept for 10s"


def custom_env_var_echo_hanler(event, context):
    return os.environ.get("CustomEnvVar")


def env_var_echo_hanler(event, context):
    return dict(os.environ)


def write_to_stderr(event, context):
    sys.stderr.write("Docker Lambda is writing to stderr")

    return "wrote to stderr"


def write_to_stdout(event, context):
    sys.stdout.write("Docker Lambda is writing to stdout")

    return "wrote to stdout"


def echo_event(event, context):
    return event


def raise_exception(event, context):
    raise Exception("Lambda is raising an exception")


def execute_git(event, context):
    return_code = subprocess.call(['git', 'init', '/tmp/samtesting'])
    assert return_code == 0

    return "git init passed"
