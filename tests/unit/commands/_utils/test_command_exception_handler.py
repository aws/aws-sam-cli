from typing import Callable
from unittest import TestCase

from botocore.exceptions import NoRegionError, ClientError, NoCredentialsError

from samcli.commands._utils.command_exception_handler import (
    command_exception_handler,
    CustomExceptionHandler,
    GenericExceptionHandler,
)
from samcli.commands.exceptions import RegionError, AWSServiceClientError, UserException, SDKError


@command_exception_handler
def echo_command(proxy_function: Callable):
    return proxy_function()


class UnhandledException(Exception):
    pass


class TestCommandExceptionHandler(TestCase):
    def test_no_exception(self):
        self.assertEqual(echo_command(lambda: 5), 5)

    def test_no_region_error(self):
        def _proxy_function_that_raises_region_error():
            raise NoRegionError()

        with self.assertRaises(RegionError):
            echo_command(_proxy_function_that_raises_region_error)

    def test_generic_sdk_error(self):
        def _proxy_function_that_raises_generic_boto_error():
            raise NoCredentialsError()

        with self.assertRaises(SDKError):
            echo_command(_proxy_function_that_raises_generic_boto_error)

    def test_aws_client_service_error(self):
        def _proxy_function_that_raises_expired_token():
            # Error code does not matter.
            raise ClientError({"Error": {"Code": "Mock Code"}}, "mock")

        with self.assertRaises(AWSServiceClientError):
            echo_command(_proxy_function_that_raises_expired_token)

    def test_unhandled_exception(self):
        def _proxy_function_that_raises_unhandled_exception():
            raise UnhandledException()

        with self.assertRaises(UnhandledException):
            echo_command(_proxy_function_that_raises_unhandled_exception)


class CustomException(Exception):
    pass


class CustomUserException(UserException):
    pass


def _custom_handler(ex: CustomException):
    raise CustomUserException("Error")


@command_exception_handler({CustomException: _custom_handler})
def command_with_custom_exception_handler(proxy_function: Callable):
    proxy_function()


class TestCommandExceptionHandlerWithCustomHandler(TestCase):
    def test_custom_exception(self):
        def _proxy_custom_exception():
            raise CustomException()

        with self.assertRaises(CustomUserException):
            command_with_custom_exception_handler(_proxy_custom_exception)


class TestCustomExceptionHandler(TestCase):
    def test_custom_exception_handler(self):
        custom_exception_handler = CustomExceptionHandler({CustomException: _custom_handler})

        self.assertEqual(custom_exception_handler.get_handler(CustomException), _custom_handler)


class TestGenericExceptionHandler(TestCase):
    def test_generc_exception_handler(self):
        def _generic_handler():
            pass

        generic_exception_handler = GenericExceptionHandler({Exception: _generic_handler})

        # CustomException is a subclass of Exception
        self.assertEqual(generic_exception_handler.get_handler(CustomException), _generic_handler)
