"""Example demonstrating parallel operations for concurrent execution."""

from typing import Any

from aws_durable_execution_sdk_python.config import ParallelConfig
from aws_durable_execution_sdk_python.context import DurableContext
from aws_durable_execution_sdk_python.execution import durable_execution
from aws_durable_execution_sdk_python.config import Duration


@durable_execution
def handler(_event: Any, context: DurableContext) -> list[str]:
    """Execute multiple operations in parallel using context.parallel()."""

    # Use context.parallel() to execute functions concurrently and extract results immediately
    return context.parallel(
        functions=[
            lambda ctx: ctx.step(lambda _: "task 1 completed", name="task1"),
            lambda ctx: ctx.step(lambda _: "task 2 completed", name="task2"),
            lambda ctx: (
                ctx.wait(Duration.from_seconds(1), name="wait_in_task3"),
                "task 3 completed after wait",
            )[1],
        ],
        name="parallel_operation",
        config=ParallelConfig(max_concurrency=2),
    ).get_results()
