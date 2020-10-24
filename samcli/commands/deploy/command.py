"""
CLI command for "deploy" command
"""
import logging

import click

from samcli.cli.cli_config_file import TomlProvider, configuration_option
from samcli.cli.main import aws_creds_options, common_options, pass_context
from samcli.commands._utils.options import (
    capabilities_override_option,
    guided_deploy_stack_name,
    metadata_override_option,
    notification_arns_override_option,
    parameter_override_option,
    no_progressbar_option,
    tags_override_option,
    template_click_option,
)
from samcli.commands.deploy.utils import sanitize_parameter_overrides
from samcli.lib.telemetry.metrics import track_command
from samcli.lib.utils import osutils
from samcli.lib.bootstrap.bootstrap import manage_stack

SHORT_HELP = "Deploy an AWS SAM application."


HELP_TEXT = """The sam deploy command creates a Cloudformation Stack and deploys your resources.

\b
e.g. sam deploy --template-file packaged.yaml --stack-name sam-app --capabilities CAPABILITY_IAM

\b
"""

CONFIG_SECTION = "parameters"
LOG = logging.getLogger(__name__)


@click.command(
    "deploy",
    short_help=SHORT_HELP,
    context_settings={"ignore_unknown_options": False, "allow_interspersed_args": True, "allow_extra_args": True},
    help=HELP_TEXT,
)
@configuration_option(provider=TomlProvider(section=CONFIG_SECTION))
@click.option(
    "--guided",
    "-g",
    required=False,
    is_flag=True,
    is_eager=True,
    help="Specify this flag to allow SAM CLI to guide you through the deployment using guided prompts.",
)
@template_click_option(include_build=True)
@click.option(
    "--stack-name",
    required=False,
    callback=guided_deploy_stack_name,
    help="The name of the AWS CloudFormation stack you're deploying to. "
    "If you specify an existing stack, the command updates the stack. "
    "If you specify a new stack, the command creates it.",
)
@click.option(
    "--s3-bucket",
    required=False,
    help="The name of the S3 bucket where this command uploads your "
    "CloudFormation template. This is required the deployments of "
    "templates sized greater than 51,200 bytes",
)
@click.option(
    "--force-upload",
    required=False,
    is_flag=True,
    help="Indicates whether to override existing files in the S3 bucket. "
    "Specify this flag to upload artifacts even if they "
    "match existing artifacts in the S3 bucket.",
)
@click.option(
    "--s3-prefix",
    required=False,
    help="A prefix name that the command adds to the "
    "artifacts' name when it uploads them to the S3 bucket. "
    "The prefix name is a path name (folder name) for the S3 bucket.",
)
@click.option(
    "--kms-key-id",
    required=False,
    help="The ID of an AWS KMS key that the command uses to encrypt artifacts that are at rest in the S3 bucket.",
)
@click.option(
    "--no-execute-changeset",
    required=False,
    is_flag=True,
    help="Indicates whether to execute the change set. "
    "Specify this flag if you want to view your stack changes "
    "before executing the change set. The command creates an AWS CloudFormation "
    "change set and then exits without executing the change set. if "
    "the changeset looks satisfactory, the stack changes can be made by "
    "running the same command without specifying `--no-execute-changeset`",
)
@click.option(
    "--role-arn",
    required=False,
    help="The Amazon Resource Name (ARN) of an  AWS  Identity "
    "and  Access  Management (IAM) role that AWS CloudFormation assumes when "
    "executing the change set.",
)
@click.option(
    "--fail-on-empty-changeset/--no-fail-on-empty-changeset",
    default=True,
    required=False,
    is_flag=True,
    help="Specify  if  the CLI should return a non-zero exit code if there are no "
    "changes to be made to the stack. The default behavior is to return a "
    "non-zero exit code.",
)
@click.option(
    "--confirm-changeset/--no-confirm-changeset",
    default=False,
    required=False,
    is_flag=True,
    help="Prompt to confirm if the computed changeset is to be deployed by SAM CLI.",
)
@click.option(
    "--use-json",
    required=False,
    is_flag=True,
    help="Indicates whether to use JSON as the format for "
    "the output AWS CloudFormation template. YAML is used by default.",
)
@click.option(
    "--resolve-s3",
    required=False,
    is_flag=True,
    help="Automatically resolve s3 bucket for non-guided deployments."
    "Do not use --s3-guided parameter with this option.",
)
@metadata_override_option
@notification_arns_override_option
@tags_override_option
@parameter_override_option
@no_progressbar_option
@capabilities_override_option
@aws_creds_options
@common_options
@pass_context
@track_command
def cli(
    ctx,
    template_file,
    stack_name,
    s3_bucket,
    force_upload,
    no_progressbar,
    s3_prefix,
    kms_key_id,
    parameter_overrides,
    capabilities,
    no_execute_changeset,
    role_arn,
    notification_arns,
    fail_on_empty_changeset,
    use_json,
    tags,
    metadata,
    guided,
    confirm_changeset,
    resolve_s3,
    config_file,
    config_env,
):

    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing
    do_cli(
        template_file,
        stack_name,
        s3_bucket,
        force_upload,
        no_progressbar,
        s3_prefix,
        kms_key_id,
        parameter_overrides,
        capabilities,
        no_execute_changeset,
        role_arn,
        notification_arns,
        fail_on_empty_changeset,
        use_json,
        tags,
        metadata,
        guided,
        confirm_changeset,
        ctx.region,
        ctx.profile,
        resolve_s3,
        config_file,
        config_env,
    )  # pragma: no cover


def do_cli(
    template_file,
    stack_name,
    s3_bucket,
    force_upload,
    no_progressbar,
    s3_prefix,
    kms_key_id,
    parameter_overrides,
    capabilities,
    no_execute_changeset,
    role_arn,
    notification_arns,
    fail_on_empty_changeset,
    use_json,
    tags,
    metadata,
    guided,
    confirm_changeset,
    region,
    profile,
    resolve_s3,
    config_file,
    config_env,
):
    from samcli.commands.package.package_context import PackageContext
    from samcli.commands.deploy.deploy_context import DeployContext
    from samcli.commands.deploy.guided_context import GuidedContext
    from samcli.commands.deploy.exceptions import DeployResolveS3AndS3SetError

    if guided:
        # Allow for a guided deploy to prompt and save those details.
        guided_context = GuidedContext(
            template_file=template_file,
            stack_name=stack_name,
            s3_bucket=s3_bucket,
            s3_prefix=s3_prefix,
            region=region,
            profile=profile,
            confirm_changeset=confirm_changeset,
            capabilities=capabilities,
            parameter_overrides=parameter_overrides,
            config_section=CONFIG_SECTION,
            config_env=config_env,
            config_file=config_file,
        )
        guided_context.run()
    elif resolve_s3 and bool(s3_bucket):
        raise DeployResolveS3AndS3SetError()
    elif resolve_s3:
        s3_bucket = manage_stack(profile=profile, region=region)
        click.echo(f"\n\t\tManaged S3 bucket: {s3_bucket}")
        click.echo("\t\tA different default S3 bucket can be set in samconfig.toml")
        click.echo("\t\tOr by specifying --s3-bucket explicitly.")

    with osutils.tempfile_platform_independent() as output_template_file:

        with PackageContext(
            template_file=template_file,
            s3_bucket=guided_context.guided_s3_bucket if guided else s3_bucket,
            s3_prefix=guided_context.guided_s3_prefix if guided else s3_prefix,
            output_template_file=output_template_file.name,
            kms_key_id=kms_key_id,
            use_json=use_json,
            force_upload=force_upload,
            no_progressbar=no_progressbar,
            metadata=metadata,
            on_deploy=True,
            region=guided_context.guided_region if guided else region,
            profile=profile,
        ) as package_context:
            package_context.run()

        with DeployContext(
            template_file=output_template_file.name,
            stack_name=guided_context.guided_stack_name if guided else stack_name,
            s3_bucket=guided_context.guided_s3_bucket if guided else s3_bucket,
            force_upload=force_upload,
            no_progressbar=no_progressbar,
            s3_prefix=guided_context.guided_s3_prefix if guided else s3_prefix,
            kms_key_id=kms_key_id,
            parameter_overrides=sanitize_parameter_overrides(guided_context.guided_parameter_overrides)
            if guided
            else parameter_overrides,
            capabilities=guided_context.guided_capabilities if guided else capabilities,
            no_execute_changeset=no_execute_changeset,
            role_arn=role_arn,
            notification_arns=notification_arns,
            fail_on_empty_changeset=fail_on_empty_changeset,
            tags=tags,
            region=guided_context.guided_region if guided else region,
            profile=profile,
            confirm_changeset=guided_context.confirm_changeset if guided else confirm_changeset,
        ) as deploy_context:
            deploy_context.run()
