"""
A list of helper functions that cleanup the processing in IntrinsicResolver and IntrinsicSymbolTable
"""
from samcli.lib.intrinsic_resolver.invalid_intrinsic_exception import InvalidIntrinsicException


def verify_intrinsic_type_bool(argument, property_type="", message="", position_in_list=""):  # type: ignore[no-untyped-def]
    verify_intrinsic_type(argument, property_type, message, position_in_list, primitive_type=bool)  # type: ignore[no-untyped-call]


def verify_intrinsic_type_list(argument, property_type="", message="", position_in_list=""):  # type: ignore[no-untyped-def]
    verify_intrinsic_type(argument, property_type, message, position_in_list, primitive_type=list)  # type: ignore[no-untyped-call]


def verify_intrinsic_type_dict(argument, property_type="", message="", position_in_list=""):  # type: ignore[no-untyped-def]
    verify_intrinsic_type(argument, property_type, message, position_in_list, primitive_type=dict)  # type: ignore[no-untyped-call]


def verify_intrinsic_type_int(argument, property_type="", message="", position_in_list=""):  # type: ignore[no-untyped-def]
    # Special case since bool is a subclass of int in python
    if isinstance(argument, bool):
        raise InvalidIntrinsicException(
            message or "The {} argument to {} must resolve to a {} type".format(position_in_list, property_type, int)
        )
    verify_intrinsic_type(argument, property_type, message, position_in_list, primitive_type=int)  # type: ignore[no-untyped-call]


def verify_intrinsic_type_str(argument, property_type="", message="", position_in_list=""):  # type: ignore[no-untyped-def]
    verify_intrinsic_type(argument, property_type, message, position_in_list, primitive_type=str)  # type: ignore[no-untyped-call]


def verify_non_null(argument, property_type="", message="", position_in_list=""):  # type: ignore[no-untyped-def]
    if argument is None:
        raise InvalidIntrinsicException(
            message
            or "The {} argument to {} is missing from the intrinsic function".format(position_in_list, property_type)
        )


def verify_intrinsic_type(argument, property_type="", message="", position_in_list="", primitive_type=str):  # type: ignore[no-untyped-def]
    verify_non_null(argument, property_type, message, position_in_list)  # type: ignore[no-untyped-call]
    if not isinstance(argument, primitive_type):
        raise InvalidIntrinsicException(
            message
            or "The {} argument to {} must resolve to a {} type".format(position_in_list, property_type, primitive_type)
        )


def verify_in_bounds(objects, index, property_type=""):  # type: ignore[no-untyped-def]
    if index < 0 or index >= len(objects):
        raise InvalidIntrinsicException(
            "The index of {} resolved properties must be within the range".format(property_type)
        )


def verify_number_arguments(arguments, property_type="", num=0):  # type: ignore[no-untyped-def]
    if not len(arguments) == num:
        raise InvalidIntrinsicException(
            "The arguments to {} must have {} arguments instead of {} arguments".format(
                property_type, num, len(arguments)
            )
        )


def verify_all_list_intrinsic_type(arguments, verification_func, property_type="", message="", position_in_list=""):  # type: ignore[no-untyped-def]
    for argument in arguments:
        verification_func(argument, property_type, message, position_in_list)
