"""
Contains asyncio related methods and helpers
"""
import asyncio
import logging
from concurrent.futures.thread import ThreadPoolExecutor
from functools import partial

LOG = logging.getLogger(__name__)


async def _run_given_tasks_async(tasks, event_loop=asyncio.get_event_loop(), executor=None):
    """
    Given list of Task objects, this method executes all tasks in the given event loop (or default one)
    and returns list of the results.
    The list of the results are in the same order as the list of the input.

    Ex; If we say we are going to execute
    Task1, Task2 and Task3; and their results are Result1, Result2 and Result3.
    If the input of the task array is; [Task1, Task2, Task3]
    The result of this operation would be; [Result1, Result2, Result3]

    If any of the tasks throws an exception, this method raise the exception to the caller

    Parameters
    ----------
    tasks : list of Task
        The list of tasks that will be executed

    event_loop: EventLoop
        The EventLoop instance that will be used for execution. If nothing is provided, this will be the default one

    executor: ThreadPoolExecutor
        The Executor that will be used by the EventLoop to execute the input tasks

    Returns
    --------
    results : list of results that is returned by the list of Tasks in order. Raises an exception if the underlying
    task is thrown an exception during its execution
    """
    async_tasks = []
    results = []

    LOG.debug("Async execution started")

    for task in tasks:
        # loop in all tasks and pass them to the executor
        LOG.debug("Invoking function %s", str(task))
        async_tasks.append(event_loop.run_in_executor(executor, task))

    LOG.debug("Waiting for async results")

    for result in await asyncio.gather(*async_tasks, return_exceptions=True):
        # for each task, wait for them to complete
        if isinstance(result, Exception):
            LOG.debug("Exception raised during the execution")
            # if the result is a type of Exception, stop the event loop and raise it back to caller
            raise result
        results.append(result)

    LOG.debug("Async execution completed")

    # flush all loggers which is printed during async execution
    if logging.root and logging.root.handlers:
        for handler in logging.root.handlers:
            handler.flush()

    return results


def run_given_tasks_async(tasks, event_loop=asyncio.get_event_loop(), executor=None):
    """
    Runs the given list of tasks in the given (or default) event loop.
    This function will wait for execution to be completed

    See _run_given_tasks_async for details

    Parameters
    ----------
    tasks: list of Task definitions that will be executed

    event_loop: EventLoop instance that will be used to execute these tasks

    executor: ThreadPoolExecutor that will be used by the EventLoop to execute the input tasks

    Returns
    -------
    List of results from the given Task list. Raises the exception if any of the underlying functions throw one
    """
    return event_loop.run_until_complete(_run_given_tasks_async(tasks, event_loop, executor))


class AsyncContext:
    """
    A helper class to hold list of tasks, and manages their execution
    """

    def __init__(self):
        self._async_tasks = []
        self.executor = None

    def add_async_task(self, function, *args):
        """
        Add a function definition and its args to the the async context, which will be executed later

        Parameters
        ----------
        function: Reference to the function definition which will be executed in this AsyncContext

        args: Parameters of the function which will be executed
        """
        self._async_tasks.append(partial(function, *args))

    def run_async(self, default_executor=True):
        """
        Will run all collected functions in async context, and return their results in order

        Parameters
        ----------
        default_executor: bool
            Determines if the async object will run using the default executor, or with a new created executor

        Returns
        -------
        List of result of the executions in order
        """
        event_loop = asyncio.new_event_loop()
        if not default_executor:
            with ThreadPoolExecutor() as self.executor:
                return run_given_tasks_async(self._async_tasks, event_loop, self.executor)
        return run_given_tasks_async(self._async_tasks, event_loop)
