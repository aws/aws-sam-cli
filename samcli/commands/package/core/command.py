"""
`sam package` command class for help text visual layer.
"""
import click
from click import Context, style
from rich.table import Table

from samcli.cli.core.command import CoreCommand
from samcli.cli.row_modifiers import RowDefinition, ShowcaseRowModifier
from samcli.commands.package.core.formatters import PackageCommandHelpTextFormatter
from samcli.commands.package.core.options import OPTIONS_INFO
from samcli.lib.utils.resources import resources_generator

COL_SIZE_MODIFIER = 38


class PackageCommand(CoreCommand):
    """
    `sam` package specific command class that specializes in the visual appearance
    of `sam package` help text.
    It hosts a custom formatter, examples, table for supported resources, acronyms
    and how options are to be used in the CLI for `sam package`.
    """

    class CustomFormatterContext(Context):
        formatter_class = PackageCommandHelpTextFormatter

    context_class = CustomFormatterContext

    @staticmethod
    def format_examples(ctx: Context, formatter: PackageCommandHelpTextFormatter):
        with formatter.indented_section(name="Examples", extra_indents=1):
            with formatter.indented_section(name="Automatic resolution of S3 buckets", extra_indents=1):
                formatter.write_rd(
                    [
                        RowDefinition(
                            text="\n",
                        ),
                        RowDefinition(
                            name=style(f"$ {ctx.command_path} --resolve-s3"),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ],
                    col_max=COL_SIZE_MODIFIER,
                )
            with formatter.indented_section(name="Get packaged template", extra_indents=1):
                formatter.write_rd(
                    [
                        RowDefinition(
                            text="\n",
                        ),
                        RowDefinition(
                            name=style(f"$ {ctx.command_path} --resolve-s3 --output-template-file packaged.yaml"),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ],
                    col_max=COL_SIZE_MODIFIER,
                )
            with formatter.indented_section(name="Customized location for uploading artifacts", extra_indents=1):
                formatter.write_rd(
                    [
                        RowDefinition(
                            text="\n",
                        ),
                        RowDefinition(
                            name=style(
                                f"$ {ctx.command_path} --s3-bucket S3_BUCKET --output-template-file packaged.yaml"
                            ),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ],
                    col_max=COL_SIZE_MODIFIER,
                )

    @staticmethod
    def format_table(formatter: PackageCommandHelpTextFormatter):
        with formatter.section(name="Supported Resources"):
            pass
        ctx = click.get_current_context()
        table = Table(width=ctx.max_content_width)
        table.add_column("Resource")
        table.add_column("Location")
        for resource, location in resources_generator():
            table.add_row(resource, location)
        with ctx.obj.console.capture() as capture:
            ctx.obj.console.print(table)
        formatter.write_rd(
            [
                RowDefinition(name="\n"),
                RowDefinition(name=capture.get()),
            ],
            col_max=COL_SIZE_MODIFIER,
        )

    @staticmethod
    def format_acronyms(formatter: PackageCommandHelpTextFormatter):
        with formatter.indented_section(name="Acronyms", extra_indents=1):
            formatter.write_rd(
                [
                    RowDefinition(
                        text="\n",
                    ),
                    RowDefinition(
                        name="S3",
                        text="Simple Storage Service",
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
                ],
                col_max=COL_SIZE_MODIFIER,
            )

    def format_options(self, ctx: Context, formatter: PackageCommandHelpTextFormatter) -> None:  # type:ignore
        # `ignore` is put in place here for mypy even though it is the correct behavior,
        # as the `formatter_class` can be set in subclass of Command. If ignore is not set,
        # mypy raises argument needs to be HelpFormatter as super class defines it.

        self.format_description(formatter)
        PackageCommand.format_examples(ctx, formatter)
        PackageCommand.format_table(formatter)
        PackageCommand.format_acronyms(formatter)

        CoreCommand._format_options(
            ctx=ctx,
            params=self.get_params(ctx),
            formatter=formatter,
            formatting_options=OPTIONS_INFO,
            write_rd_overrides={"col_max": COL_SIZE_MODIFIER},
        )
