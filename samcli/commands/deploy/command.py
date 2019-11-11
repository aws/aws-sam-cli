"""
CLI command for "deploy" command
"""

import tempfile

import click

from samcli.commands._utils.options import (
    parameter_override_option,
    capabilities_override_option,
    tags_override_option,
    notification_arns_override_option,
    template_click_option,
    metadata_override_option)
from samcli.cli.cli_config_file import configuration_option, TomlProvider
from samcli.cli.main import pass_context, common_options, aws_creds_options
from samcli.lib.telemetry.metrics import track_command


SHORT_HELP = "Deploy an AWS SAM application."


HELP_TEXT = """The sam deploy command creates a Cloudformation Stack and deploys your resources.

\b
e.g. sam deploy --template-file packaged.yaml --stack-name sam-app --capabilities CAPABILITY_IAM

\b
"""


@configuration_option(provider=TomlProvider(section="parameters"))
@click.command(
    "deploy",
    short_help=SHORT_HELP,
    context_settings={"ignore_unknown_options": False, "allow_interspersed_args": True, "allow_extra_args": True},
    help=HELP_TEXT,
)
@template_click_option(include_build=False)
@click.option(
    "--stack-name",
    required=True,
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
    "Specify this flag to upload artifacts even if they"
    "match existing artifacts in the S3 bucket.",
)
@click.option(
    "--s3-prefix",
    required=False,
    help="A prefix name that the command adds to the "
    "artifacts' name when it uploads them to the S3 bucket."
    "The prefix name is a path name (folder name) for the S3 bucket.",
)
@click.option(
    "--kms-key-id",
    required=False,
    help="The ID of an AWS KMS key that the command uses" " to encrypt artifacts that are at rest in the S3 bucket.",
)
@click.option(
    "--no-execute-changeset",
    required=False,
    is_flag=True,
    help="Indicates  whether  to  execute  the"
    "change  set.  Specify  this flag if you want to view your stack changes"
    "before executing the change set. The command creates an AWS CloudForma-"
    "tion  change set and then exits without executing the change set. if "
    "the changeset looks satisfactory, the stack changes can be made by "
    "running the same command without specifying `--no-execute-changeset`",
)
@click.option(
    "--role-arn",
    required=False,
    help="The Amazon Resource Name (ARN) of an  AWS  Identity"
    "and  Access  Management (IAM) role that AWS CloudFormation assumes when"
    "executing the change set.",
)
@click.option(
    "--fail-on-empty-changeset",
    required=False,
    is_flag=True,
    help="Specify  if  the CLI should return a non-zero exit code if there are no"
    "changes to be made to the stack. The default behavior is  to  return  a"
    "non-zero exit code.",
)
@click.option(
    "--use-json",
    required=False,
    is_flag=True,
    help="Indicates whether to use JSON as the format for "
    "the output AWS CloudFormation template. YAML is used by default.",
)
@metadata_override_option
@notification_arns_override_option
@tags_override_option
@parameter_override_option
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
):

    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing
    do_cli(
        template_file,
        stack_name,
        s3_bucket,
        force_upload,
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
        ctx.region,
        ctx.profile,
    )  # pragma: no cover


def do_cli(
    template_file,
    stack_name,
    s3_bucket,
    force_upload,
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
    region,
    profile,
):
    from samcli.commands.package.package_context import PackageContext
    from samcli.commands.deploy.deploy_context import DeployContext

    with tempfile.NamedTemporaryFile() as output_template_file:

        with PackageContext(
            template_file=template_file,
            s3_bucket=s3_bucket,
            s3_prefix=s3_prefix,
            output_template_file=output_template_file.name,
            kms_key_id=kms_key_id,
            use_json=use_json,
            force_upload=force_upload,
            metadata=metadata,
            on_deploy=True,
            region=region,
            profile=profile
        ) as package_context:
            package_context.run()

        with DeployContext(
            template_file=output_template_file.name,
            stack_name=stack_name,
            s3_bucket=s3_bucket,
            force_upload=force_upload,
            s3_prefix=s3_prefix,
            kms_key_id=kms_key_id,
            parameter_overrides=parameter_overrides,
            capabilities=capabilities,
            no_execute_changeset=no_execute_changeset,
            role_arn=role_arn,
            notification_arns=notification_arns,
            fail_on_empty_changeset=fail_on_empty_changeset,
            tags=tags,
            region=region,
            profile=profile,
        ) as deploy_context:
            deploy_context.run()
