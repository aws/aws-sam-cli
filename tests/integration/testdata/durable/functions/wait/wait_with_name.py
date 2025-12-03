from typing import Any

from aws_durable_execution_sdk_python.context import DurableContext
from aws_durable_execution_sdk_python.execution import durable_execution
from aws_durable_execution_sdk_python.config import Duration


@durable_execution
def handler(event: Any, context: DurableContext) -> str:
    # Wait with explicit name, using wait_seconds from event or default to 2
    wait_seconds = event.get("wait_seconds", 2) if isinstance(event, dict) else 2
    context.wait(Duration.from_seconds(wait_seconds), name="custom_wait")
    return "Wait with name completed"
