"""
Module to check mutually exclusive cli parameters
"""
from typing import List

import click


class Mutex(click.Option):
    """
    Preprocessing checks for mutually exclusive or required parameters as supported by click api.
    """

    def __init__(self, *args, **kwargs):
        self.required_param_lists: List = kwargs.pop("required_param_lists", None)
        self.required_params_hint: str = kwargs.pop("required_params_hint", None)
        self.incompatible_params: List = kwargs.pop("incompatible_params", None)
        self.incompatible_params_hint: str = kwargs.pop("incompatible_params_hint", None)

        super().__init__(*args, **kwargs)

    def handle_parse_result(self, ctx, opts, args):
        if self.name not in opts:
            return super().handle_parse_result(ctx, opts, args)

        # Check for parameters not compatible with each other
        for incompatible_param in self.incompatible_params or []:
            if incompatible_param in opts:
                msg = (
                    f"You must not provide both the {Mutex._to_param_name(self.name)} and ",
                    f"{Mutex._to_param_name(incompatible_param)} parameters.\n",
                )
                if self.incompatible_params_hint:
                    msg += self.incompatible_params_hint
                raise click.UsageError(msg)

        # Check for required parameters
        if self.required_param_lists:
            missing_param_lists = list()
            for required_params in self.required_param_lists:
                missing_params = list()
                for required_param in required_params:
                    if required_param not in opts:
                        missing_params.append(required_param)
                if missing_params:
                    missing_param_lists.append(missing_params)

            if missing_param_lists:
                msg = (
                    f"Missing required parameters, with --{self.name.replace('_', '-')} set.\n",
                    "Must provide one of the following required parameter combinations:\n",
                )
                for missing_params in missing_param_lists:
                    msg += "\t"
                    msg += ", ".join(Mutex._to_param_name(param) for param in missing_params)
                    msg += "\n"

                if self.required_params_hint:
                    msg += self.required_params_hint
                raise click.UsageError(msg)
            self.prompt = None

        return super().handle_parse_result(ctx, opts, args)

    @staticmethod
    def _to_param_name(param: str):
        return f"--{param.replace('_', '-')}"
