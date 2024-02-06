"""
A list of helper functions that cleanup the processing in IntrinsicResolver and IntrinsicSymbolTable
"""

from samcli.lib.intrinsic_resolver.invalid_intrinsic_exception import InvalidIntrinsicException


def verify_intrinsic_type_bool(argument, property_type="", message="", position_in_list=""):
    verify_intrinsic_type(argument, property_type, message, position_in_list, primitive_type=bool)


def verify_intrinsic_type_list(argument, property_type="", message="", position_in_list=""):
    verify_intrinsic_type(argument, property_type, message, position_in_list, primitive_type=list)


def verify_intrinsic_type_dict(argument, property_type="", message="", position_in_list=""):
    verify_intrinsic_type(argument, property_type, message, position_in_list, primitive_type=dict)


def verify_intrinsic_type_int(argument, property_type="", message="", position_in_list=""):
    # Special case since bool is a subclass of int in python
    if isinstance(argument, bool):
        raise InvalidIntrinsicException(
            message or "The {} argument to {} must resolve to a {} type".format(position_in_list, property_type, int)
        )
    verify_intrinsic_type(argument, property_type, message, position_in_list, primitive_type=int)


def verify_intrinsic_type_str(argument, property_type="", message="", position_in_list=""):
    verify_intrinsic_type(argument, property_type, message, position_in_list, primitive_type=str)


def verify_non_null(argument, property_type="", message="", position_in_list=""):
    if argument is None:
        raise InvalidIntrinsicException(
            message
            or "The {} argument to {} is missing from the intrinsic function".format(position_in_list, property_type)
        )


def verify_intrinsic_type(argument, property_type="", message="", position_in_list="", primitive_type=str):
    verify_non_null(argument, property_type, message, position_in_list)
    if not isinstance(argument, primitive_type):
        raise InvalidIntrinsicException(
            message
            or "The {} argument to {} must resolve to a {} type".format(position_in_list, property_type, primitive_type)
        )


def verify_in_bounds(objects, index, property_type=""):
    if index < 0 or index >= len(objects):
        raise InvalidIntrinsicException(
            "The index of {} resolved properties must be within the range".format(property_type)
        )


def verify_number_arguments(arguments, property_type="", num=0):
    if not len(arguments) == num:
        raise InvalidIntrinsicException(
            "The arguments to {} must have {} arguments instead of {} arguments".format(
                property_type, num, len(arguments)
            )
        )


def verify_all_list_intrinsic_type(arguments, verification_func, property_type="", message="", position_in_list=""):
    for argument in arguments:
        verification_func(argument, property_type, message, position_in_list)
