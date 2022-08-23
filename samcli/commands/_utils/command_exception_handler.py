"""
Contains method decorator which can be used to convert common exceptions into click exceptions
which will end exeecution gracefully
"""
from functools import wraps
from typing import Callable, Dict, Any, Optional

from botocore.exceptions import NoRegionError, ClientError

from samcli.commands._utils.options import parameterized_option
from samcli.commands.exceptions import CredentialsError, RegionError
from samcli.lib.utils.boto_utils import get_client_error_code


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

                # if no custom handling defined search for default handlers
                exception_handler = COMMON_EXCEPTION_HANDLER_MAPPING.get(exception_type)
                if exception_handler:
                    exception_handler(ex)

                # if no handler defined, raise the exception
                raise ex

        return wrapper_command_exception_handler

    return decorator_command_exception_handler(f)


def _handle_no_region_error(ex: NoRegionError) -> None:
    raise RegionError(
        "No region information found. Please provide --region parameter or configure default region settings. "
        "\nFor more information please visit https://docs.aws.amazon.com/sdk-for-java/v1/developer-guide/"
        "setup-credentials.html#setup-credentials-setting-region"
    )


def _handle_client_errors(ex: ClientError) -> None:
    error_code = get_client_error_code(ex)

    if error_code in ("ExpiredToken", "ExpiredTokenException"):
        raise CredentialsError(
            "Your credential configuration is invalid or has expired token value. \nFor more information please "
            "visit: https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html"
        )

    raise ex


COMMON_EXCEPTION_HANDLER_MAPPING: Dict[Any, Callable] = {
    NoRegionError: _handle_no_region_error,
    ClientError: _handle_client_errors,
}
