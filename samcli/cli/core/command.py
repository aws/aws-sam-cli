"""
Core command class that inherits from click.Command and overrides some of the formatting options
to be specific for AWS SAM CLI.

Should be used by all commands for a consistent UI experience
"""
from typing import Any, Dict, List, Optional

from click import Command, Context, Parameter, style

from samcli.cli.formatters import RootCommandHelpTextFormatter
from samcli.cli.row_modifiers import RowDefinition


class CoreCommand(Command):
    def __init__(self, description, requires_credentials=False, *args, **kwargs):
        self.description = description
        self.requires_credentials = requires_credentials
        self.description_addendum = (
            style("\n  This command requires access to AWS credentials.", bold=True)
            if self.requires_credentials
            else style("\n  This command may not require access to AWS credentials.", bold=True)
        )
        super().__init__(*args, **kwargs)

    def format_description(self, formatter: RootCommandHelpTextFormatter):
        with formatter.indented_section(name="Description", extra_indents=1):
            formatter.write_rd(
                [
                    RowDefinition(
                        text="",
                        name=self.description + self.description_addendum,
                    ),
                ],
            )

    @staticmethod
    def _format_options(
        ctx: Context,
        params: List[Parameter],
        formatter: RootCommandHelpTextFormatter,
        formatting_options: Dict[str, Dict],
        write_rd_overrides: Optional[Dict[str, Any]] = None,
    ):
        write_rd_overrides = write_rd_overrides or {}
        for option_heading, options in formatting_options.items():
            opts: List[RowDefinition] = sorted(
                [
                    CoreCommand.convert_param_to_row_definition(
                        ctx=ctx, param=param, rank=options.get("option_names", {}).get(param.name, {}).get("rank", 0)
                    )
                    for param in params
                    if param.name in options.get("option_names", {}).keys()
                ],
                key=lambda row_def: row_def.rank,
            )
            with formatter.indented_section(name=option_heading, extra_indents=1):
                formatter.write_rd(options.get("extras", [RowDefinition()]), **write_rd_overrides)
                formatter.write_rd(
                    [RowDefinition(name="", text="\n")]
                    + [
                        opt
                        for options in zip(opts, [RowDefinition(name="", text="\n")] * (len(opts)))
                        for opt in options
                    ],
                    **write_rd_overrides,
                )

    @staticmethod
    def convert_param_to_row_definition(ctx: Context, param: Parameter, rank: int):
        help_record = param.get_help_record(ctx)
        if not help_record:
            return RowDefinition()
        name, text = help_record
        return RowDefinition(name=name, text=text, rank=rank)
