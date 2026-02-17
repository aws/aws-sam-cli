from click import Context, style

from samcli.cli.core.command import CoreCommand
from samcli.cli.row_modifiers import RowDefinition, ShowcaseRowModifier
from samcli.commands.common.formatters import CommandHelpTextFormatter
from samcli.commands.deploy.core.options import ALL_OPTIONS, OPTIONS_INFO

COL_SIZE_MODIFIER = 38


class DeployCommand(CoreCommand):
    class CustomFormatterContext(Context):
        def make_formatter(self):
            return CommandHelpTextFormatter(
                options=ALL_OPTIONS,
                width=self.terminal_width,
                max_width=self.max_content_width,
            )

    context_class = CustomFormatterContext

    @staticmethod
    def format_examples(ctx: Context, formatter: CommandHelpTextFormatter):
        with formatter.indented_section(name="Examples", extra_indents=1):
            with formatter.indented_section(name="Deploy with guided prompts", extra_indents=1):
                formatter.write_rd(
                    [
                        RowDefinition(
                            text="\n",
                        ),
                        RowDefinition(
                            name=style(f"$ {ctx.command_path} --guided"),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )
            with formatter.indented_section(name="Deploy with specified parameters", extra_indents=1):
                formatter.write_rd(
                    [
                        RowDefinition(
                            text="\n",
                        ),
                        RowDefinition(
                            name=style(
                                f"$ {ctx.command_path} --template-file packaged.yaml --stack-name "
                                f"sam-app --capabilities CAPABILITY_IAM"
                            ),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )
            with formatter.indented_section(
                name="Deploy with parameter overrides using CloudFormation syntax", extra_indents=1
            ):
                formatter.write_rd(
                    [
                        RowDefinition(
                            text="\n",
                        ),
                        RowDefinition(
                            name=style(
                                f"$ {ctx.command_path} --parameter-overrides "
                                f"'ParameterKey=InstanceType,ParameterValue=t1.micro'"
                            ),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )
            with formatter.indented_section(
                name="Deploy with parameter overrides using shorthand syntax", extra_indents=1
            ):
                formatter.write_rd(
                    [
                        RowDefinition(
                            text="\n",
                        ),
                        RowDefinition(
                            name=style(
                                f"$ {ctx.command_path} --parameter-overrides KeyPairName=MyKey InstanceType=t1.micro"
                            ),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )

    @staticmethod
    def format_acronyms(formatter: CommandHelpTextFormatter):
        with formatter.indented_section(name="Acronyms", extra_indents=1):
            formatter.write_rd(
                [
                    RowDefinition(
                        text="\n",
                    ),
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
                ],
                col_max=COL_SIZE_MODIFIER,
            )

    def format_options(self, ctx: Context, formatter: CommandHelpTextFormatter) -> None:  # type:ignore
        # `ignore` is put in place here for mypy even though it is the correct behavior,
        # as the `formatter_class` can be set in subclass of Command. If ignore is not set,
        # mypy raises argument needs to be HelpFormatter as super class defines it.

        self.format_description(formatter)
        DeployCommand.format_examples(ctx, formatter)
        DeployCommand.format_acronyms(formatter)

        CoreCommand._format_options(
            ctx=ctx,
            params=self.get_params(ctx),
            formatter=formatter,
            formatting_options=OPTIONS_INFO,
            write_rd_overrides={"col_max": COL_SIZE_MODIFIER},
        )
