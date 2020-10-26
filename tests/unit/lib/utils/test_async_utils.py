from unittest import TestCase
from time import sleep, time

from parameterized import parameterized

from samcli.lib.utils.async_utils import AsyncContext


# List of methods which will be used during the tests
def hello_world():
    return "Hello World"


def hello_message(message):
    return f"Hello {message}"


def raises_exception():
    raise Exception


def wait_for_seconds(seconds_to_wait):
    sleep(seconds_to_wait)
    return "Hello World"


class TestAsyncContext(TestCase):
    @parameterized.expand([(hello_world, {}, "Hello World"), (hello_message, {"Mars"}, "Hello Mars")])
    def test_async_execution_will_return_expected_results(self, function_ref, params, expected):
        async_context = AsyncContext()
        async_context.add_async_task(function_ref, params)

        results = async_context.run_async()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], expected)

    def test_async_execution_will_raise_exception(self):
        async_context = AsyncContext()
        async_context.add_async_task(raises_exception)

        self.assertRaises(Exception, async_context.run_async)

    @parameterized.expand([(1,), (2,), (4,), (8,), (16,)])
    def test_tasks_should_execute_in_parallel(self, number_of_executions):
        seconds_to_wait = 1
        async_context = AsyncContext()
        for _ in range(number_of_executions):
            async_context.add_async_task(wait_for_seconds, {seconds_to_wait})

        start_time = time()
        async_context.run_async()
        end_time = time()

        self.assertLess((end_time - start_time), (seconds_to_wait + 1))
