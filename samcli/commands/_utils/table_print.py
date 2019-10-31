from functools import wraps

import click


def pprint(format_string, format_kwargs):
    def pprint_wrap(func):
        # Calculate terminal width, number of columns in the table
        width, _ = click.get_terminal_size()
        total_args = len(format_kwargs)

        # Get width to be a usable number so that we can equally divide the space for all the columns
        width = width - (width % total_args)
        usable_width = int(width) - 1
        width_per_column = int(width / total_args)

        # The final column should not roll over into the next line
        final_arg_width = width_per_column - 1

        # the format string contains minimumwidth that need to be set.
        # eg: "{a:{0}}} {b:<{1}}} {c:{2}}}"
        format_args = [width_per_column for _ in range(total_args - 1)]
        format_args.extend([final_arg_width])

        # format arguments are now ready for setting minimumwidth

        @wraps(func)
        def wrap(*args, **kwargs):
            # The table is setup with the column names, format_string contains the column names.
            click.secho("-" * usable_width)
            click.secho(format_string.format(*format_args, **format_kwargs))
            click.secho("-" * usable_width)
            # format_args which have the minimumwidth set per {} in the format_string is passed to the function
            # which this decorator wraps, so that the function has access to the correct format_args
            kwargs["format_args"] = format_args
            result = func(*args, **kwargs)
            # Complete the table
            click.secho("-" * usable_width)
            return result

        return wrap

    return pprint_wrap
