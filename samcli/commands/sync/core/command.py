"""
Sync Command Class.
"""
from typing import List

from click import Command, Context, Parameter, style

from samcli.cli.row_modifiers import RowDefinition, ShowcaseRowModifier
from samcli.commands.sync.core.formatters import SyncCommandHelpTextFormatter
from samcli.commands.sync.core.options import OPTIONS_INFO


class SyncCommand(Command):
    class CustomFormatterContext(Context):
        formatter_class = SyncCommandHelpTextFormatter

    context_class = CustomFormatterContext

    def __init__(self, description, requires_credentials=False, *args, **kwargs):
        self.description = description
        self.requires_credentials = requires_credentials
        self.description_addendum = (
            style("\n  This command requires access to AWS credentials.", bold=True)
            if self.requires_credentials
            else style("\n  This command does not require access to AWS credentials.", bold=True)
        )
        super().__init__(*args, **kwargs)

    def format_description(self, formatter: SyncCommandHelpTextFormatter):
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
    def format_examples(ctx: Context, formatter: SyncCommandHelpTextFormatter):
        with formatter.indented_section(name="Examples", extra_indents=1):
            formatter.write_rd(
                [
                    RowDefinition(
                        text="\n",
                    ),
                    RowDefinition(
                        name=style(f"${ctx.command_path} " f"--watch --stack-name {{stack}}"),
                        extra_row_modifiers=[ShowcaseRowModifier()],
                    ),
                    RowDefinition(
                        name=style(f"${ctx.command_path} " f"--code --watch --stack-name {{stack}}"),
                        extra_row_modifiers=[ShowcaseRowModifier()],
                    ),
                    RowDefinition(
                        name=style(
                            f"${ctx.command_path} "
                            f"--code --stack-name {{stack}} --resource-id {{ChildStack}}/{{ResourceId}} "
                        ),
                        extra_row_modifiers=[ShowcaseRowModifier()],
                    ),
                ],
            )

    @staticmethod
    def format_acronyms(formatter: SyncCommandHelpTextFormatter):
        with formatter.indented_section(name="Acronyms", extra_indents=1):
            formatter.write_rd(
                [
                    RowDefinition(
                        name="IAM",
                        text="Identity and Access Management",
                        extra_row_modifiers=[ShowcaseRowModifier()],
                    ),
                    RowDefinition(
                        name="ARN",
                        text="Amazon Resource Name",
                        extra_row_modifiers=[ShowcaseRowModifier()],
                    ),
                    RowDefinition(
                        name="S3",
                        text="Simple Storage Service",
                        extra_row_modifiers=[ShowcaseRowModifier()],
                    ),
                    RowDefinition(
                        name="SNS",
                        text="Simple Notification Service",
                        extra_row_modifiers=[ShowcaseRowModifier()],
                    ),
                    RowDefinition(
                        name="ECR",
                        text="Elastic Container Registry",
                        extra_row_modifiers=[ShowcaseRowModifier()],
                    ),
                    RowDefinition(
                        name="KMS",
                        text="Key Management Service",
                        extra_row_modifiers=[ShowcaseRowModifier()],
                    ),
                ]
            )

    def format_options(self, ctx: Context, formatter: SyncCommandHelpTextFormatter) -> None:  # type:ignore
        # NOTE(sriram-mv): `ignore` is put in place here for mypy even though it is the correct behavior,
        # as the `formatter_class` can be set in subclass of Command. If ignore is not set,
        # mypy raises argument needs to be HelpFormatter as super class defines it.

        self.format_description(formatter)
        SyncCommand.format_examples(ctx, formatter)
        SyncCommand.format_acronyms(formatter)

        params = self.get_params(ctx)

        for option_heading, options in OPTIONS_INFO.items():
            opts: List[RowDefinition] = sorted(
                [
                    SyncCommand._convert_param_to_row_definition(
                        ctx=ctx, param=param, rank=options.get("option_names", {}).get(param.name, {}).get("rank", 0)
                    )
                    for param in params
                    if param.name in options.get("option_names", {}).keys()
                ],
                key=lambda row_def: row_def.rank,
            )
            with formatter.indented_section(name=option_heading, extra_indents=1):
                formatter.write_rd(options.get("extras", [RowDefinition()]))
                formatter.write_rd(
                    [RowDefinition(name="", text="\n")]
                    + [
                        opt
                        for options in zip(opts, [RowDefinition(name="", text="\n")] * (len(opts)))
                        for opt in options
                    ]
                )

    @staticmethod
    def _convert_param_to_row_definition(ctx: Context, param: Parameter, rank: int):
        help_record = param.get_help_record(ctx)
        if not help_record:
            return RowDefinition()
        name, text = help_record
        return RowDefinition(name=name, text=text, rank=rank)
