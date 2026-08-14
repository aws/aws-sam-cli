import logging
from typing import Any

from aws_durable_execution_sdk_python.config import WaitForCallbackConfig
from aws_durable_execution_sdk_python.context import (
    DurableContext,
    WaitForCallbackContext,
)
from aws_durable_execution_sdk_python.execution import durable_execution
from aws_durable_execution_sdk_python.config import Duration

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def external_system_call(callback_id: str, _context: WaitForCallbackContext) -> None:
    logger.info(f"Waiting for callback: {callback_id}")


@durable_execution
def handler(event: Any, context: DurableContext) -> str:
    config = WaitForCallbackConfig(
        timeout=Duration.from_seconds(5),
        heartbeat_timeout=Duration.from_seconds(3),
    )

    result = context.wait_for_callback(
        external_system_call, name="external_call", config=config
    )

    return f"External system result: {result}"
