"""
Module to check mutually exclusive cli parameters
"""
from typing import List

import click


class Mutex(click.Option):
    """
    Preprocessing checks for mutually explicit or required parameters as supported by click api.
    """

    def __init__(self, *args, **kwargs):
        self.required_params: List = kwargs.pop("required_params", None)
        self.not_required: List = kwargs.pop("not_required", None)

        super().__init__(*args, **kwargs)

    def handle_parse_result(self, ctx, opts, args):
        current_opt: bool = self.name in opts
        # Check for parameters not compatible with each other
        for mutex_opt in self.not_required or []:
            if mutex_opt in opts:
                if current_opt:
                    msg = f"""
You must not provide both the --{self.name.replace("_", "-")} and --{str(mutex_opt).replace("_", "-")} parameters.

You can run 'sam init' without any options for an interactive initialization flow, or you can provide one of the following required parameter combinations:
    --name and --runtime and --app-template and --dependency-manager
    --name and --package-type and --base-image
    --location
                            """
                    raise click.UsageError(msg)
                self.prompt = None
        # check for required parameters
        if self.required_params:
            req_flag = True
            for mutex_opt_list in self.required_params:
                req_cnt = len(mutex_opt_list)
                for mutex_opt in mutex_opt_list:
                    if mutex_opt in opts:
                        req_cnt -= 1

                if not req_cnt:
                    req_flag = False

            if current_opt and req_flag:
                msg = f"""
Missing required parameters, with --{self.name.replace("_", "-")} set.

Must provide one of the following required parameter combinations:
    --name and --runtime and --dependency-manager and --app-template
    --name and --package-type and --base-image and --dependency-manager
    --location

You can also re-run without the --no-interactive flag to be prompted for required values.
                """
                raise click.UsageError(msg)
            self.prompt = None
        return super().handle_parse_result(ctx, opts, args)
