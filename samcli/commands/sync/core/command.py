import click
from click import Command, Context

from samcli.cli.formatters import RootCommandHelpTextFormatter
from samcli.cli.row_modifiers import RowDefinition, ShowcaseRowModifier
from samcli.commands.sync.core.formatters import SyncCommandHelpTextFormatter

DESCRIPTION = """
  By default, the sync command runs a full AWS Cloudformation stack update. 
  You can specify --code or --watch to switch modes. 
  Sync also supports nested stacks and nested stack resources.

  Running --watch with --code option will provide a way to run code
  synchronization only speeding up start time and will skip any
  template change. Please remember to update the deployed stack by running
  without --code option.
  
  """ + click.style(
    "This command requires access to AWS credentials.", bold=True
)

REQUIRED_OPTIONS = ["stack_name", "template_file"]

CREDENTIAL_OPTION_NAMES = ["region", "profile"]

INFRASTRUCTURE_OPTION_NAMES = [
    "parameter_overrides",
    "capabilities",
    "s3_bucket",
    "s3_prefix",
    "image_repository",
    "image_repositories",
    "kms_key_id",
    "role_arn",
    "notification_arns",
    "tags",
    "metadata",
]

CONFIGURATION_OPTION_NAMES = ["config_env", "config_file"]

ADDITIONAL_OPTIONS = [
    "dependency_layer",
    "no_dependency_layer",
    "watch",
    "code",
    "resource_id",
    "resource",
    "use_container",
    "base_dir",
]
OTHER_OPTIONS = ["debug", "help"]


class SyncCommand(Command):
    class CustomFormatterContext(Context):
        formatter_class = SyncCommandHelpTextFormatter

    context_class = CustomFormatterContext

    def format_options(self, ctx: Context, formatter: RootCommandHelpTextFormatter) -> None:
        # NOTE(sriram-mv): ALL OF BELOW CODE IS EXTREMELY HACKY AND WILL GET REWRITTEN.
        # it only serves as something to show how the help text looks like.
        opts = [RowDefinition(name="", text="\n")]
        required_opts = [RowDefinition(name="", text="\n")]
        cred_opts = [RowDefinition(name="", text="\n")]
        infra_opts = [RowDefinition(name="", text="\n")]
        config_opts = [RowDefinition(name="", text="\n")]
        additional_opts = [RowDefinition(name="", text="\n")]
        other_opts = [RowDefinition(name="", text="\n")]

        for param in self.get_params(ctx):
            row = param.get_help_record(ctx)
            if row is not None:
                term, help_text = row
                if param.name in REQUIRED_OPTIONS:
                    required_opts.append(RowDefinition(name=term, text=help_text))
                    continue
                if param.name in CREDENTIAL_OPTION_NAMES:
                    cred_opts.append(RowDefinition(name=term, text=help_text))
                    continue
                if param.name in INFRASTRUCTURE_OPTION_NAMES:
                    infra_opts.append(RowDefinition(name=term, text=help_text))
                    continue
                if param.name in CONFIGURATION_OPTION_NAMES:
                    config_opts.append(RowDefinition(name=term, text=help_text))
                    continue
                if param.name in ADDITIONAL_OPTIONS:
                    additional_opts.append(RowDefinition(name=term, text=help_text))
                    continue
                if param.name in OTHER_OPTIONS:
                    other_opts.append(RowDefinition(name=term, text=help_text))
                    continue
                else:
                    opts.append(RowDefinition(name=term, text=help_text))

        with formatter.indented_section(name="Description", extra_indents=1):
            formatter.write_rd(
                [
                    RowDefinition(
                        text="",
                        name=DESCRIPTION,
                    ),
                ],
            )

        with formatter.indented_section(name="Examples", extra_indents=1):
            formatter.write_rd(
                [
                    RowDefinition(
                        name="",
                        text="\n",
                    ),
                    RowDefinition(
                        text="",
                        name=click.style(f"${ctx.command_path} " f"--code --watch --stack-name {{stack}}"),
                        extra_row_modifiers=[ShowcaseRowModifier()],
                    ),
                    RowDefinition(
                        text="",
                        name=click.style(
                            f"${ctx.command_path} "
                            f"--code --stack-name {{stack}} --resource-id {{ChildStack}}/{{ResourceId}} "
                        ),
                        extra_row_modifiers=[ShowcaseRowModifier()],
                    ),
                ],
            )

        with formatter.indented_section(name="Acronyms", extra_indents=1):
            formatter.write_rd(
                [
                    RowDefinition(
                        name="IAM:",
                        text="Identity and Access Management.",
                        extra_row_modifiers=[ShowcaseRowModifier()],
                    ),
                    RowDefinition(
                        name="ARN:",
                        text="Amazon Resource Name.",
                        extra_row_modifiers=[ShowcaseRowModifier()],
                    ),
                    RowDefinition(
                        name="SNS:",
                        text="Simple Notification Service",
                        extra_row_modifiers=[ShowcaseRowModifier()],
                    ),
                    RowDefinition(
                        name="ECR:",
                        text="Elastic Container Registry",
                        extra_row_modifiers=[ShowcaseRowModifier()],
                    ),
                    RowDefinition(
                        name="KMS:",
                        text="Key Management Service",
                        extra_row_modifiers=[ShowcaseRowModifier()],
                    ),
                ]
            )

        if required_opts:
            with formatter.indented_section(name="Required Options", extra_indents=1):
                formatter.write_rd(required_opts)

        if cred_opts:
            with formatter.indented_section(name="AWS Credential Options", extra_indents=1):
                formatter.write_rd(cred_opts)
        if infra_opts:
            with formatter.indented_section(name="Infrastructure Options", extra_indents=1):
                formatter.write_rd(infra_opts)
        if config_opts:
            with formatter.indented_section(name="Infrastructure Options", extra_indents=1):
                formatter.write_rd(config_opts)
        if additional_opts:
            with formatter.indented_section(name="Additional Options", extra_indents=1):
                formatter.write_rd(additional_opts)
        if other_opts:
            with formatter.indented_section(name="Other Options", extra_indents=1):
                formatter.write_rd(other_opts)
