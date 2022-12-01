"""
Contains method decorator which can be used to convert common exceptions into click exceptions
which will end exeecution gracefully
"""
from functools import wraps
from typing import Callable, Dict, Any, Optional

from botocore.exceptions import NoRegionError, ClientError

from samcli.commands._utils.parameterized_option import parameterized_option
from samcli.commands.exceptions import CredentialsError, RegionError
from samcli.lib.utils.boto_utils import get_client_error_code


@parameterized_option  # type: ignore[misc]
def command_exception_handler(f, additional_mapping: Optional[Dict[Any, Callable[[Any], None]]] = None):  # type: ignore[no-untyped-def, no-untyped-def]
    """
    This function returns a wrapped function definition, which handles configured exceptions gracefully
    """

    def decorator_command_exception_handler(func):  # type: ignore[no-untyped-def]
        @wraps(func)
        def wrapper_command_exception_handler(*args, **kwargs):  # type: ignore[no-untyped-def]
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

    return decorator_command_exception_handler(f)  # type: ignore[no-untyped-call]


def _handle_no_region_error(ex: NoRegionError) -> None:
    raise RegionError(  # type: ignore[no-untyped-call]
        "No region information found. Please provide --region parameter or configure default region settings. "
        "\nFor more information please visit https://docs.aws.amazon.com/sdk-for-java/v1/developer-guide/"
        "setup-credentials.html#setup-credentials-setting-region"
    )


def _handle_client_errors(ex: ClientError) -> None:
    error_code = get_client_error_code(ex)

    if error_code in ("ExpiredToken", "ExpiredTokenException"):
        raise CredentialsError(  # type: ignore[no-untyped-call]
            "Your credential configuration is invalid or has expired token value. \nFor more information please "
            "visit: https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html"
        )

    raise ex


COMMON_EXCEPTION_HANDLER_MAPPING: Dict[Any, Callable] = {  # type: ignore[type-arg]
    NoRegionError: _handle_no_region_error,
    ClientError: _handle_client_errors,
}
