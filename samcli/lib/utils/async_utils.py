"""
Contains asyncio related methods and helpers
"""
import asyncio
import logging

LOG = logging.getLogger(__name__)


async def _run_given_tasks_async(tasks, event_loop=asyncio.get_event_loop()):
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

    Returns
    --------
    results : list of results that is returned by the list of Tasks in order. Raises an exception if the underlying
    task is thrown an exception during its execution
    """
    async_tasks = []
    results = []

    for task in tasks:
        # loop in all tasks and pass them to the executor
        async_tasks.append(event_loop.run_in_executor(None, task.function, *task.args))

    for result in await asyncio.gather(*async_tasks, return_exceptions=True):
        # for each task, wait for them to complete
        if isinstance(result, Exception):
            # if the result is a type of Exception, stop the event loop and raise it back to caller
            raise result
        results.append(result)

    return results


def run_given_tasks_async(tasks, event_loop=asyncio.get_event_loop()):
    """
    Runs the given list of tasks in the given (or default) event loop.
    This function will wait for execution to be completed

    See _run_given_tasks_async for details

    Parameters
    ----------
    tasks: list of Task definitions that will be executed

    event_loop: EventLoop instance that will be used to execute these tasks

    Returns
    -------
    List of results from the given Task list. Raises the exception if any of the underlying functions throw one
    """
    return event_loop.run_until_complete(_run_given_tasks_async(tasks, event_loop))


class AsyncContext:
    """
    A helper class to hold list of tasks, and manages their execution
    """

    def __init__(self):
        self._async_tasks = []

    def add_async_task(self, function, args=tuple()):
        """
        Add a function definition and its args to the the async context, which will be executed later

        Parameters
        ----------
        function: Reference to the function definition which will be executed in this AsyncContext

        args: Parameters of the function which will be executed
        """
        self._async_tasks.append(Task(function, args))

    def run_async(self):
        """
        Will run all collected functions in async context, and return their results in order

        Returns
        -------
        List of result of the executions in order
        """
        event_loop = asyncio.new_event_loop()
        return run_given_tasks_async(self._async_tasks, event_loop)


class Task:
    """
    This class is used to define a task which consists of a function definition and the parameters
    """

    def __init__(self, function, args=tuple()):
        self.function = function
        self.args = args

    def execute(self):
        """
        Executes given function definition with arguments and returns its result
        """
        return self.function(*self.args)
