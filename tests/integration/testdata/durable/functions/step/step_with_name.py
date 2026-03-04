from typing import Any

from aws_durable_execution_sdk_python.context import DurableContext
from aws_durable_execution_sdk_python.execution import durable_execution


@durable_execution
def handler(_event: Any, context: DurableContext) -> str:
    # Step with explicit name
    result = context.step(lambda _: "Step with explicit name", name="custom_step")
    return f"Result: {result}"
