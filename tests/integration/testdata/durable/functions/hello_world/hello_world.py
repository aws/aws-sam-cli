from typing import Any
import json

from aws_durable_execution_sdk_python.context import DurableContext
from aws_durable_execution_sdk_python.execution import durable_execution


@durable_execution
def handler(_event: Any, context: DurableContext) -> dict:
    return {
        "statusCode": 200,
        "body": json.dumps({"message": "Hello, World!"})
    }
