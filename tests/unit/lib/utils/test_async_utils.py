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
    @parameterized.expand([(hello_world, None, "Hello World"), (hello_message, "Mars", "Hello Mars")])
    def test_async_execution_will_return_expected_results(self, function_ref, params, expected):
        async_context = AsyncContext()
        if params:
            async_context.add_async_task(function_ref, params)
        else:
            async_context.add_async_task(function_ref)

        results = async_context.run_async()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], expected)

    def test_async_execution_will_raise_exception(self):
        async_context = AsyncContext()
        async_context.add_async_task(raises_exception)

        self.assertRaises(Exception, async_context.run_async)
