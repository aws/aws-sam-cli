"""
CLI command for "deploy" command
"""
import tempfile
import json
import click
from click.types import FuncParamType

from samcli.commands._utils.options import (
    parameter_override_option,
    capabilities_override_option,
    tags_override_option,
    notification_arns_override_option,
    template_click_option,
    metadata_override_option,
    _space_separated_list_func_type,
)
from samcli.cli.cli_config_file import configuration_option, TomlProvider
from samcli.cli.main import pass_context, common_options, aws_creds_options
from samcli.lib.telemetry.metrics import track_command
from samcli.lib.utils.colors import Colored
from samcli.lib.bootstrap.bootstrap import manage_stack
from samcli.lib.config.samconfig import SamConfig
from samcli.cli.context import get_cmd_names


SHORT_HELP = "Deploy an AWS SAM application."


HELP_TEXT = """The sam deploy command creates a Cloudformation Stack and deploys your resources.

\b
e.g. sam deploy --template-file packaged.yaml --stack-name sam-app --capabilities CAPABILITY_IAM

\b
"""

CONFIG_SECTION = "parameters"


@click.command(
    "deploy",
    short_help=SHORT_HELP,
    context_settings={"ignore_unknown_options": False, "allow_interspersed_args": True, "allow_extra_args": True},
    help=HELP_TEXT,
)
@configuration_option(provider=TomlProvider(section=CONFIG_SECTION))
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
    help="The ID of an AWS KMS key that the command uses to encrypt artifacts that are at rest in the S3 bucket.",
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
    "--confirm-changeset",
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
    confirm_changeset,
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
        confirm_changeset,
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
    confirm_changeset,
    region,
    profile,
):
    from samcli.commands.package.package_context import PackageContext
    from samcli.commands.deploy.deploy_context import DeployContext

    # set capabilities and changeset decision to None, before interactive gets input from the user
    changeset_decision = None
    _capabilities = None

    if interactive:
        stack_name, s3_bucket, region, profile, changeset_decision, _capabilities, save_to_config = guided_deploy(
            stack_name, s3_bucket, region, profile, confirm_changeset
        )

        if save_to_config:
            save_config(
                template_file,
                stack_name=stack_name,
                s3_bucket=s3_bucket,
                region=region,
                profile=profile,
                confirm_changeset=confirm_changeset,
                capabilities=_capabilities,
            )

        # We print deploy args only on interactive.
        # Should we print this always?
        print_deploy_args(
            stack_name=stack_name,
            s3_bucket=s3_bucket,
            region=region,
            profile=profile,
            capabilities=_capabilities,
            parameter_overrides=parameter_overrides,
            confirm_changeset=changeset_decision,
        )

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
            capabilities=_capabilities if interactive else capabilities,
            no_execute_changeset=no_execute_changeset,
            role_arn=role_arn,
            notification_arns=notification_arns,
            fail_on_empty_changeset=fail_on_empty_changeset,
            tags=tags,
            region=region,
            profile=profile,
            confirm_changeset=changeset_decision if interactive else confirm_changeset,
        ) as deploy_context:
            deploy_context.run()


def guided_deploy(stack_name, s3_bucket, region, profile, confirm_changeset):
    default_region = region or "us-east-1"
    default_capabilities = ("CAPABILITY_IAM",)
    input_capabilities = None

    color = Colored()
    tick = color.yellow("✓")

    click.echo(
        color.yellow("\n\tSetting default arguments for 'sam deploy'\n\t=========================================")
    )

    stack_name = click.prompt(f"\t{tick} Stack Name", default=stack_name, type=click.STRING)
    region = click.prompt(f"\t{tick} AWS Region", default=default_region, type=click.STRING)
    click.secho("\t#Shows you resources changes to be deployed and require a 'Y' to initiate deploy")
    confirm_changeset = click.confirm(f"\t{tick} Confirm changes before deploy", default=confirm_changeset)
    click.secho("\t#SAM needs permission to be able to create roles to connect to the resources in your template")
    capabilities_confirm = click.confirm(f"\t{tick} Allow SAM CLI IAM role creation", default=True)

    if not capabilities_confirm:
        input_capabilities = click.prompt(
            f"\t{tick} Capabilities",
            default=default_capabilities,
            type=FuncParamType(func=_space_separated_list_func_type),
        )

    save_to_config = click.confirm(f"\t{tick} Save arguments to samconfig.toml", default=True)

    if not s3_bucket:
        click.echo(color.yellow("\n\tConfiguring Deployment S3 Bucket\n\t================================"))
        s3_bucket = manage_stack(profile=profile, region=region)
        click.echo(f"\t{tick} Using Deployment Bucket: {s3_bucket}")
        click.echo("\tYou may specify a different default deployment bucket in samconfig.toml")

    return (
        stack_name,
        s3_bucket,
        region,
        profile,
        confirm_changeset,
        input_capabilities if input_capabilities else default_capabilities,
        save_to_config,
    )


def print_deploy_args(stack_name, s3_bucket, region, profile, capabilities, parameter_overrides, confirm_changeset):

    param_overrides_string = json.dumps(parameter_overrides, indent=2)
    capabilities_string = json.dumps(capabilities)

    click.secho("\n\tDeploying with following values\n\t===============================", fg="yellow")
    click.echo(f"\tStack Name                 : {stack_name}")
    click.echo(f"\tRegion                     : {region}")
    click.echo(f"\tProfile                    : {profile}")
    click.echo(f"\tDeployment S3 Bucket       : {s3_bucket}")
    click.echo(f"\tParameter Overrides        : {param_overrides_string}")
    click.echo(f"\tCapabilities               : {capabilities_string}")
    click.echo(f"\tConfirm Changeset          : {confirm_changeset}")

    click.secho("\n\tInitiating Deployment\n\t=====================", fg="yellow")


def save_config(template_file, **kwargs):
    color = Colored()
    tick = color.yellow("✓")

    section = CONFIG_SECTION
    ctx = click.get_current_context()

    samconfig_dir = getattr(ctx, "samconfig_dir", None)
    samconfig = SamConfig(
        config_dir=samconfig_dir if samconfig_dir else SamConfig.config_dir(template_file_path=template_file)
    )

    cmd_names = get_cmd_names(ctx.info_name, ctx)

    for key, value in kwargs.items():
        if isinstance(value, (list, tuple)):
            value = " ".join(val for val in value)
        samconfig.put(cmd_names, section, key, value)

    samconfig.flush()

    click.echo(f"\n\t{tick} Saved arguments to config file")
    click.echo("\tRunning 'sam deploy' for future deployments will use the parameters saved above.")
    click.echo("\tThe above parameters can be changed by modifying samconfig.toml")
    click.echo("\tLearn more about samconfig.toml syntax http://url")
