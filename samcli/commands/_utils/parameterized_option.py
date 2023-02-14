"""
Parameterized Option Class
"""

import types


def parameterized_option(option):
    """Meta decorator for option decorators.
    This adds the ability to specify optional parameters for option decorators.

    Usage:
        @parameterized_option
        def some_option(f, required=False)
            ...

        @some_option
        def command(...)

        or

        @some_option(required=True)
        def command(...)
    """

    def parameter_wrapper(*args, **kwargs):
        if len(args) == 1 and isinstance(args[0], types.FunctionType):
            # Case when option decorator does not have parameter
            # @stack_name_option
            # def command(...)
            return option(args[0])

        # Case when option decorator does have parameter
        # @stack_name_option("a", "b")
        # def command(...)

        def option_wrapper(f):
            return option(f, *args, **kwargs)

        return option_wrapper

    return parameter_wrapper
