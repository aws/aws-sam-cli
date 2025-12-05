import logging
from typing import Any

from aws_durable_execution_sdk_python.config import WaitForCallbackConfig
from aws_durable_execution_sdk_python.context import DurableContext
from aws_durable_execution_sdk_python.execution import durable_execution
from aws_durable_execution_sdk_python.config import Duration

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def external_system_call(callback_id: str) -> None:
    """Simulate calling an external system with callback ID."""
    # In real usage, this would make an API call to an external system
    # passing the callback_id for the system to call back when done
    logger.info(f"Waiting for callback: {callback_id}")


@durable_execution
def handler(event: Any, context: DurableContext) -> str:
    timeout_seconds = event.get("timeout_seconds", 120)
    heartbeat_timeout_seconds = event.get("heartbeat_timeout_seconds", 60)
    
    config = WaitForCallbackConfig(
        timeout=Duration.from_seconds(timeout_seconds), 
        heartbeat_timeout=Duration.from_seconds(heartbeat_timeout_seconds)
    )

    result = context.wait_for_callback(
        external_system_call, name="external_call", config=config
    )

    return f"External system result: {result}"
