"""Example demonstrating map operations for processing collections durably."""

from typing import Any

from aws_durable_execution_sdk_python.config import MapConfig
from aws_durable_execution_sdk_python.context import DurableContext
from aws_durable_execution_sdk_python.execution import durable_execution


@durable_execution
def handler(_event: Any, context: DurableContext) -> list[int]:
    """Process a list of items using context.map()."""
    items = [1, 2, 3, 4, 5]

    # Use context.map() to process items concurrently and extract results immediately
    return context.map(
        inputs=items,
        func=lambda ctx, item, index, _: ctx.step(
            lambda _: item * 2, name=f"map_item_{index}"
        ),
        name="map_operation",
        config=MapConfig(max_concurrency=2),
    ).get_results()
