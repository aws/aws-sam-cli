"""
CLI command for "deploy" command
"""

import tempfile
import json
import click

from samcli.commands._utils.options import (
    parameter_override_option,
    capabilities_override_option,
    tags_override_option,
    notification_arns_override_option,
    template_click_option,
    metadata_override_option,
)
from samcli.cli.cli_config_file import configuration_option, TomlProvider
from samcli.cli.main import pass_context, common_options, aws_creds_options
from samcli.lib.telemetry.metrics import track_command
from samcli.lib.utils.colors import Colored
from samcli.lib.bootstrap.bootstrap import manage_stack


SHORT_HELP = "Deploy an AWS SAM application."


HELP_TEXT = """The sam deploy command creates a Cloudformation Stack and deploys your resources.

\b
e.g. sam deploy --template-file packaged.yaml --stack-name sam-app --capabilities CAPABILITY_IAM

\b
"""


def prompt_callback(msg, default):
    def callback(ctx, param, value):
        interactive = ctx.params.get("interactive")

        if interactive:
            param.prompt = msg
            param.default = value or default
            return param.prompt_for_value(ctx)
        elif value:
            # Value provided + No Interactive. Return the value
            return value
        else:
            # Value not provided + No Interactive
            raise click.exceptions.MissingParameter(param=param, ctx=ctx)

    return callback


@click.command(
    "deploy",
    short_help=SHORT_HELP,
    context_settings={"ignore_unknown_options": False, "allow_interspersed_args": True, "allow_extra_args": True},
    help=HELP_TEXT,
)
@configuration_option(provider=TomlProvider(section="parameters"))
@template_click_option(include_build=True)
@click.option(
    "--stack-name",
    required=False,
    default="sam-app",
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
@click.option(
    "--interactive",
    "-i",
    required=False,
    is_flag=True,
    is_eager=True,
    help="Specify this flag to allow SAM CLI to guide you through the deployment using interactive prompts.",
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
    interactive,
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
        interactive,
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
    interactive,
    region,
    profile,
):
    from samcli.commands.package.package_context import PackageContext
    from samcli.commands.deploy.deploy_context import DeployContext

    confirm_changeset = False
    if interactive:
        stack_name, s3_bucket, region, profile, confirm_changeset = guided_deploy(
            stack_name, s3_bucket, region, profile
        )

        # We print deploy args only on interactive.
        # Should we print this always?
        print_deploy_args(stack_name, s3_bucket, region, profile, capabilities, parameter_overrides, confirm_changeset)

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
            profile=profile,
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
            confirm_changeset=confirm_changeset,
        ) as deploy_context:
            deploy_context.run()


def guided_deploy(stack_name, s3_bucket, region, profile):
    default_region = region or "us-east-1"
    default_profile = profile or "default"

    color = Colored()
    tick = color.yellow("✓")

    click.echo(color.yellow("\nDeploy Arguments\n================"))

    stack_name = click.prompt(f"{tick} Stack Name", default=stack_name, type=click.STRING)
    confirm_changeset = click.confirm(f"{tick} Confirm changeset before deploy", default=True)
    region = click.prompt(f"{tick} AWS Region", default=default_region, type=click.STRING)
    profile = click.prompt(f"{tick} AWS Profile", default=default_profile, type=click.STRING)

    save_to_samconfig = click.confirm(f"{tick} Save values to samconfig.toml", default=True)

    if not s3_bucket:
        click.echo(color.yellow("\nConfiguring Deployment S3 Bucket\n================================"))
        s3_bucket = manage_stack(profile, region)
        click.echo(f"{tick} Using Deployment Bucket: {s3_bucket}")
        click.echo("You may specify a different default deployment bucket in samconfig.toml")

    return stack_name, s3_bucket, region, profile, confirm_changeset


def print_deploy_args(stack_name, s3_bucket, region, profile, capabilities, parameter_overrides, confirm_changeset):

    param_overrides_string = json.dumps(parameter_overrides, indent=2)
    capabilities_string = json.dumps(capabilities)

    click.secho("\nDeploying with following values\n===============================", fg="yellow")
    click.echo(f"Stack Name                 : {stack_name}")
    click.echo(f"Region                     : {region}")
    click.echo(f"Profile                    : {profile}")
    click.echo(f"Deployment S3 Bucket       : {s3_bucket}")
    click.echo(f"Parameter Overrides        : {param_overrides_string}")
    click.echo(f"Capabilities               : {capabilities_string}")
    click.echo(f"Confirm Changeset          : {confirm_changeset}")

    click.secho("\nInitiating Deployment\n=====================", fg="yellow")
