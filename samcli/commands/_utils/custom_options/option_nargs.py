"""
Custom Click options for multiple arguments
"""

import click


class OptionNargs(click.Option):
    """
    A custom option class that allows parsing for multiple arguments
    for an option, when the number of arguments for an option are unknown.
    """

    def __init__(self, *args, **kwargs):
        self.nargs = kwargs.pop("nargs", -1)
        super().__init__(*args, **kwargs)
        self._previous_parser_process = None
        self._nargs_parser = None

    def add_to_parser(self, parser, ctx):
        def parser_process(value, state):
            # look ahead into arguments till we reach the next option.
            # the next option starts with a prefix which is either '-' or '--'
            next_option = False
            value = [value]

            while state.rargs and not next_option:
                for prefix in self._nargs_parser.prefixes:
                    if state.rargs[0].startswith(prefix):
                        next_option = True
                if not next_option:
                    value.append(state.rargs.pop(0))

            value = tuple(value)

            # call the actual process
            self._previous_parser_process(value, state)

        # Add current option to Parser by calling add_to_parser on the super class.
        super().add_to_parser(parser, ctx)
        for name in self.opts:
            # Get OptionParser object for current option
            option_parser = getattr(parser, "_long_opt").get(name) or getattr(parser, "_short_opt").get(name)
            if option_parser:
                # Monkey patch `process` method for click.parser.Option class.
                # This allows for setting multiple parsed values into current option arguments
                self._nargs_parser = option_parser
                self._previous_parser_process = option_parser.process
                option_parser.process = parser_process
                break
