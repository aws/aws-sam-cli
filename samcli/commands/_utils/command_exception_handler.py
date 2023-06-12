"""
Contains method decorator which can be used to convert common exceptions into click exceptions
which will end execution gracefully
"""
from functools import wraps
from typing import Any, Callable, Dict, Optional

from botocore.exceptions import BotoCoreError, ClientError, NoRegionError

from samcli.commands._utils.parameterized_option import parameterized_option
from samcli.commands.exceptions import AWSServiceClientError, RegionError, SDKError


class CustomExceptionHandler:
    def __init__(self, custom_exception_handler_mapping):
        self.custom_exception_handler_mapping = custom_exception_handler_mapping

    def get_handler(self, exception_type: type):
        return self.custom_exception_handler_mapping.get(exception_type)


class GenericExceptionHandler:
    def __init__(self, generic_exception_handler_mapping):
        self.generic_exception_handler_mapping = generic_exception_handler_mapping

    def get_handler(self, exception_type: type):
        for common_exception, common_exception_handler in self.generic_exception_handler_mapping.items():
            if issubclass(exception_type, common_exception):
                return common_exception_handler


def _handle_no_region_error(ex: NoRegionError) -> None:
    raise RegionError(
        "No region information found. Please provide --region parameter or configure default region settings."
    )


def _handle_client_errors(ex: ClientError) -> None:
    additional_exception_message = (
        "\n\nFor more information please visit: "
        "https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html"
    )
    raise AWSServiceClientError(str(ex) + additional_exception_message) from ex


def _catch_all_boto_errors(ex: BotoCoreError) -> None:
    raise SDKError(str(ex)) from ex


CUSTOM_EXCEPTION_HANDLER_MAPPING: Dict[Any, Callable] = {
    NoRegionError: _handle_no_region_error,
    ClientError: _handle_client_errors,
}

GENERIC_EXCEPTION_HANDLER_MAPPING: Dict[Any, Callable] = {BotoCoreError: _catch_all_boto_errors}


@parameterized_option
def command_exception_handler(f, additional_mapping: Optional[Dict[Any, Callable[[Any], None]]] = None):
    """
    This function returns a wrapped function definition, which handles configured exceptions gracefully
    """

    def decorator_command_exception_handler(func):
        @wraps(func)
        def wrapper_command_exception_handler(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as ex:
                exception_type = type(ex)

                # check if there is a custom handling defined
                exception_handler = (additional_mapping or {}).get(exception_type)
                if exception_handler:
                    exception_handler(ex)

                # if no custom handling defined search for default handlers under pre-defined
                # custom and generic handlers.
                for exception_handler in [
                    CustomExceptionHandler(CUSTOM_EXCEPTION_HANDLER_MAPPING),
                    GenericExceptionHandler(GENERIC_EXCEPTION_HANDLER_MAPPING),
                ]:
                    handler = exception_handler.get_handler(exception_type)
                    if handler:
                        handler(ex)

                # if no handler defined, raise the exception
                raise ex

        return wrapper_command_exception_handler

    return decorator_command_exception_handler(f)
