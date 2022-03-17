"""
Module to check mutually exclusive cli parameters
"""
from typing import Any, List, Dict, Tuple

import click


class ClickMutex(click.Option):
    """
    Preprocessing checks for mutually exclusive or required parameters as supported by click api.

    required_param_lists: List[List[str]]
        List of lists with each supported combination of params
        Ex:
        With option = "a" and required_param_lists = [["b", "c"], ["c", "d"]]
        It is valid to specify --a --b --c or --a --c --d
        but not --a --b --d

    required_params_hint: str
        String to be appended after default missing required params prompt

    incompatible_params: List[str]
        List of incompatible parameters

    incompatible_params_hint: str
        String to be appended after default incompatible params prompt
    """

    def __init__(self, *args, **kwargs):
        self.required_param_lists: List[List[str]] = kwargs.pop("required_param_lists", [])
        self.required_params_hint: str = kwargs.pop("required_params_hint", "")
        self.incompatible_params: List[str] = kwargs.pop("incompatible_params", [])
        self.incompatible_params_hint: str = kwargs.pop("incompatible_params_hint", "")

        super().__init__(*args, **kwargs)

    def handle_parse_result(self, ctx: click.Context, opts: Dict[str, Any], args: List[str]) -> Tuple[Any, List[str]]:
        """
        Checks whether any option is in self.incompatible_params
        If one is found, prompt and throw an UsageError

        Then checks any combination in self.required_param_lists is satisfied.
        With option = "a" and required_param_lists = [["b", "c"], ["c", "d"]]
        It is valid to specify --a --b --c, --a --c --d, or --a --b --c --d
        but not --a --b --d
        """
        if self.name not in opts:
            return super().handle_parse_result(ctx, opts, args)

        # Check for parameters not compatible with each other
        for incompatible_param in self.incompatible_params:
            if incompatible_param in opts:
                msg = (
                    f"You must not provide both the {ClickMutex._to_param_name(self.name)} and "
                    f"{ClickMutex._to_param_name(incompatible_param)} parameters.\n"
                )
                msg += self.incompatible_params_hint
                raise click.UsageError(msg)

        # Check for required parameters
        if self.required_param_lists:
            # Loop through all combinations of required params
            for required_params in self.required_param_lists:
                # Test whether all required params exist in one combination/required_params
                has_all_required_params = False not in [required_param in opts for required_param in required_params]

                # Break to skip over "else" block if any one combination is satisfied
                if has_all_required_params:
                    break
            else:
                msg = (
                    f"Missing required parameters, with --{self.name.replace('_', '-')} set.\n"
                    "Must provide one of the following required parameter combinations:\n"
                )
                for required_params in self.required_param_lists:
                    msg += "\t"
                    msg += ", ".join(ClickMutex._to_param_name(param) for param in required_params)
                    msg += "\n"

                msg += self.required_params_hint
                raise click.UsageError(msg)
            self.prompt = ""

        return super().handle_parse_result(ctx, opts, args)

    @staticmethod
    def _to_param_name(param: str):
        return f"--{param.replace('_', '-')}"
