from typing import List

from click import Context, style

from samcli.cli.core.command import CoreCommand
from samcli.cli.row_modifiers import RowDefinition, ShowcaseRowModifier
from samcli.commands.init.core.formatters import InitCommandHelpTextFormatter
from samcli.commands.init.core.options import OPTIONS_INFO


class InitCommand(CoreCommand):
    class CustomFormatterContext(Context):
        formatter_class = InitCommandHelpTextFormatter

    context_class = CustomFormatterContext

    @staticmethod
    def format_examples(ctx: Context, formatter: InitCommandHelpTextFormatter):
        with formatter.indented_section(name="Examples", extra_indents=1):
            with formatter.indented_section(name="Interactive Mode", extra_indents=1):
                formatter.write_rd(
                    [
                        RowDefinition(
                            text="\n",
                        ),
                        RowDefinition(name=style(f"$ {ctx.command_path}"), extra_row_modifiers=[ShowcaseRowModifier()]),
                    ]
                )
            with formatter.indented_section(name="Customized Interactive Mode", extra_indents=1):
                formatter.write_rd(
                    [
                        RowDefinition(
                            text="\n",
                        ),
                        RowDefinition(
                            name=style(
                                f"$ {ctx.command_path} --name sam-app --runtime nodejs18.x --architecture arm64"
                            ),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                        RowDefinition(
                            name=style(
                                f"$ {ctx.command_path} --name sam-app --runtime nodejs18.x --dependency-manager "
                                f"npm --app-template hello-world"
                            ),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                        RowDefinition(
                            name=style(
                                f"$ {ctx.command_path} --name sam-app --package-type image --architecture arm64"
                            ),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )
            with formatter.indented_section(name="Direct Initialization", extra_indents=1):
                formatter.write_rd(
                    [
                        RowDefinition(
                            text="\n",
                        ),
                        RowDefinition(
                            name=style(f"$ {ctx.command_path} --location gh:aws-samples/cookiecutter-aws-sam-python"),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                        RowDefinition(
                            name=style(
                                f"$ {ctx.command_path} --location "
                                f"git+ssh://git@github.com/aws-samples/cookiecutter-aws-sam-python.git"
                            ),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                        RowDefinition(
                            name=style(f"$ {ctx.command_path} --location /path/to/template.zip"),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                        RowDefinition(
                            name=style(f"$ {ctx.command_path} --location /path/to/template/directory"),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                        RowDefinition(
                            name=style(f"$ {ctx.command_path} --location https://example.com/path/to/template.zip"),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ],
                )

    def format_options(self, ctx: Context, formatter: InitCommandHelpTextFormatter) -> None:  # type:ignore
        # `ignore` is put in place here for mypy even though it is the correct behavior,
        # as the `formatter_class` can be set in subclass of Command. If ignore is not set,
        # mypy raises argument needs to be HelpFormatter as super class defines it.

        self.format_description(formatter)
        InitCommand.format_examples(ctx, formatter)

        for option_heading, options in OPTIONS_INFO.items():
            opts: List[RowDefinition] = sorted(
                [
                    CoreCommand.convert_param_to_row_definition(
                        ctx=ctx, param=param, rank=options.get("option_names", {}).get(param.name, {}).get("rank", 0)
                    )
                    for param in self.get_params(ctx)
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
                    ],
                )
