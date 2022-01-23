import json
import sys
import time


def handler(event, context):
    return {"statusCode": 200, "body": json.dumps({"hello": "world"})}


def echo_event_handler(event, context):
    return {"statusCode": 200, "body": json.dumps(event)}


def echo_event_handler_2(event, context):
    event["handler"] = "echo_event_handler_2"

    return {"statusCode": 200, "body": json.dumps(event)}


def echo_integer_body(event, context):
    return {"statusCode": 200, "body": 42}


def content_type_setter_handler(event, context):
    return {"statusCode": 200, "body": "hello", "headers": {"Content-Type": "text/plain"}}


def only_set_status_code_handler(event, context):
    return {"statusCode": 200}


def only_set_body_handler(event, context):
    return {"body": json.dumps({"hello": "world"})}


def string_status_code_handler(event, context):
    return {"statusCode": "200", "body": json.dumps({"hello": "world"})}


def sleep_10_sec_handler(event, context):
    # sleep thread for 10s. This is useful for testing multiple requests
    time.sleep(10)

    return {"statusCode": 200, "body": json.dumps({"message": "HelloWorld! I just slept and waking up."})}


def write_to_stderr(event, context):
    sys.stderr.write("Docker Lambda is writing to stderr")

    return {"statusCode": 200, "body": json.dumps({"hello": "world"})}


def write_to_stdout(event, context):
    sys.stdout.write("Docker Lambda is writing to stdout")

    return {"statusCode": 200, "body": json.dumps({"hello": "world"})}


def invalid_response_returned(event, context):
    return "This is invalid"

def integer_response_returned(event, context):
    return 2

def invalid_v2_respose_returned(event, context):
    return {"statusCode": 200, "body": json.dumps({"hello": "world"}), "key": "value"}

def invalid_hash_response(event, context):
    return {"foo": "bar"}


def base64_response(event, context):
    gifImageBase64 = "R0lGODdhAQABAJEAAAAAAP///wAAAAAAACH5BAkAAAIALAAAAAABAAEAAAICRAEAOw=="  # NOQA

    return {
        "statusCode": 200,
        "body": gifImageBase64,
        "isBase64Encoded": True,
        "headers": {"Content-Type": "image/gif"},
    }


def echo_base64_event_body(event, context):
    return {
        "statusCode": 200,
        "body": event["body"],
        "headers": {"Content-Type": event["headers"]["Content-Type"]},
        "isBase64Encoded": event["isBase64Encoded"],
    }


def multiple_headers(event, context):
    return {
        "statusCode": 200,
        "body": "hello",
        "headers": {"Content-Type": "text/plain"},
        "multiValueHeaders": {"MyCustomHeader": ["Value1", "Value2"]},
    }


def multiple_headers_overrides_headers(event, context):
    return {
        "statusCode": 200,
        "body": "hello",
        "headers": {"Content-Type": "text/plain", "MyCustomHeader": "Custom"},
        "multiValueHeaders": {"MyCustomHeader": ["Value1", "Value2"]},
    }


def handle_options_cors(event, context):
    return {"statusCode": 204, "body": json.dumps({"hello": "world"})}
