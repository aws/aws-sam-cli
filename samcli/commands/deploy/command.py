"""
CLI command for "deploy" command
"""
import json
import logging

import click
from click.types import FuncParamType

from samcli.lib.utils import osutils
from samcli.cli.cli_config_file import configuration_option, TomlProvider
from samcli.cli.context import get_cmd_names
from samcli.cli.main import pass_context, common_options, aws_creds_options
from samcli.commands._utils.options import (
    parameter_override_option,
    capabilities_override_option,
    tags_override_option,
    notification_arns_override_option,
    template_click_option,
    metadata_override_option,
    _space_separated_list_func_type,
    guided_deploy_stack_name,
)
from samcli.commands._utils.template import get_template_parameters
from samcli.commands.deploy.exceptions import GuidedDeployFailedError
from samcli.lib.bootstrap.bootstrap import manage_stack
from samcli.lib.config.samconfig import SamConfig
from samcli.lib.telemetry.metrics import track_command
from samcli.lib.utils.colors import Colored

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
    "change  set.  Specify  this flag if you want to view your stack changes "
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
    guided,
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
        guided,
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
    guided,
    confirm_changeset,
    region,
    profile,
):
    from samcli.commands.package.package_context import PackageContext
    from samcli.commands.deploy.deploy_context import DeployContext

    # set capabilities and changeset decision to None, before guided gets input from the user
    changeset_decision = None
    _capabilities = None
    _parameter_overrides = None
    guided_stack_name = None
    guided_s3_bucket = None
    guided_s3_prefix = None
    guided_region = None

    if guided:

        try:
            _parameter_override_keys = get_template_parameters(template_file=template_file)
        except ValueError as ex:
            LOG.debug("Failed to parse SAM template", exc_info=ex)
            raise GuidedDeployFailedError(str(ex))

        read_config_showcase(template_file=template_file)

        (
            guided_stack_name,
            guided_s3_bucket,
            guided_s3_prefix,
            guided_region,
            guided_profile,
            changeset_decision,
            _capabilities,
            _parameter_overrides,
            save_to_config,
        ) = guided_deploy(
            stack_name, s3_bucket, region, profile, confirm_changeset, _parameter_override_keys, parameter_overrides
        )

        if save_to_config:
            save_config(
                template_file,
                stack_name=guided_stack_name,
                s3_bucket=guided_s3_bucket,
                s3_prefix=guided_s3_prefix,
                region=guided_region,
                profile=guided_profile,
                confirm_changeset=changeset_decision,
                capabilities=_capabilities,
                parameter_overrides=_parameter_overrides,
            )

    print_deploy_args(
        stack_name=guided_stack_name if guided else stack_name,
        s3_bucket=guided_s3_bucket if guided else s3_bucket,
        region=guided_region if guided else region,
        capabilities=_capabilities if guided else capabilities,
        parameter_overrides=_parameter_overrides if guided else parameter_overrides,
        confirm_changeset=changeset_decision if guided else confirm_changeset,
    )

    with osutils.tempfile_platform_independent() as output_template_file:

        with PackageContext(
            template_file=template_file,
            s3_bucket=guided_s3_bucket if guided else s3_bucket,
            s3_prefix=guided_s3_prefix if guided else s3_prefix,
            output_template_file=output_template_file.name,
            kms_key_id=kms_key_id,
            use_json=use_json,
            force_upload=force_upload,
            metadata=metadata,
            on_deploy=True,
            region=guided_region if guided else region,
            profile=profile,
        ) as package_context:
            package_context.run()

        with DeployContext(
            template_file=output_template_file.name,
            stack_name=guided_stack_name if guided else stack_name,
            s3_bucket=guided_s3_bucket if guided else s3_bucket,
            force_upload=force_upload,
            s3_prefix=guided_s3_prefix if guided else s3_prefix,
            kms_key_id=kms_key_id,
            parameter_overrides=sanitize_parameter_overrides(_parameter_overrides) if guided else parameter_overrides,
            capabilities=_capabilities if guided else capabilities,
            no_execute_changeset=no_execute_changeset,
            role_arn=role_arn,
            notification_arns=notification_arns,
            fail_on_empty_changeset=fail_on_empty_changeset,
            tags=tags,
            region=guided_region if guided else region,
            profile=profile,
            confirm_changeset=changeset_decision if guided else confirm_changeset,
        ) as deploy_context:
            deploy_context.run()


def guided_deploy(
    stack_name, s3_bucket, region, profile, confirm_changeset, parameter_override_keys, parameter_overrides
):
    default_stack_name = stack_name or "sam-app"
    default_region = region or "us-east-1"
    default_capabilities = ("CAPABILITY_IAM",)
    input_capabilities = None

    color = Colored()
    start_bold = "\033[1m"
    end_bold = "\033[0m"

    click.echo(
        color.yellow("\n\tSetting default arguments for 'sam deploy'\n\t=========================================")
    )

    stack_name = click.prompt(f"\t{start_bold}Stack Name{end_bold}", default=default_stack_name, type=click.STRING)
    s3_prefix = stack_name
    region = click.prompt(f"\t{start_bold}AWS Region{end_bold}", default=default_region, type=click.STRING)
    input_parameter_overrides = prompt_parameters(parameter_override_keys, start_bold, end_bold)

    click.secho("\t#Shows you resources changes to be deployed and require a 'Y' to initiate deploy")
    confirm_changeset = click.confirm(
        f"\t{start_bold}Confirm changes before deploy{end_bold}", default=confirm_changeset
    )
    click.secho("\t#SAM needs permission to be able to create roles to connect to the resources in your template")
    capabilities_confirm = click.confirm(f"\t{start_bold}Allow SAM CLI IAM role creation{end_bold}", default=True)

    if not capabilities_confirm:
        input_capabilities = click.prompt(
            f"\t{start_bold}Capabilities{end_bold}",
            default=default_capabilities[0],
            type=FuncParamType(func=_space_separated_list_func_type),
        )

    save_to_config = click.confirm(f"\t{start_bold}Save arguments to samconfig.toml{end_bold}", default=True)

    s3_bucket = manage_stack(profile=profile, region=region)
    click.echo(f"\n\t\tManaged S3 bucket: {s3_bucket}")
    click.echo("\t\tA different default S3 bucket can be set in samconfig.toml")

    return (
        stack_name,
        s3_bucket,
        s3_prefix,
        region,
        profile,
        confirm_changeset,
        input_capabilities if input_capabilities else default_capabilities,
        input_parameter_overrides if input_parameter_overrides else parameter_overrides,
        save_to_config,
    )


def prompt_parameters(parameter_override_keys, start_bold, end_bold):
    _prompted_param_overrides = {}
    if parameter_override_keys:
        for parameter_key, parameter_properties in parameter_override_keys.items():
            no_echo = parameter_properties.get("NoEcho", False)
            if no_echo:
                parameter = click.prompt(
                    f"\t{start_bold}Parameter {parameter_key}{end_bold}", type=click.STRING, hide_input=True
                )
                _prompted_param_overrides[parameter_key] = {"Value": parameter, "Hidden": True}
            else:
                # Make sure the default is casted to a string.
                parameter = click.prompt(
                    f"\t{start_bold}Parameter {parameter_key}{end_bold}",
                    default=_prompted_param_overrides.get(parameter_key, str(parameter_properties.get("Default", ""))),
                    type=click.STRING,
                )
                _prompted_param_overrides[parameter_key] = {"Value": parameter, "Hidden": False}
    return _prompted_param_overrides


def print_deploy_args(stack_name, s3_bucket, region, capabilities, parameter_overrides, confirm_changeset):

    _parameters = parameter_overrides.copy()
    for key, value in _parameters.items():
        if isinstance(value, dict):
            _parameters[key] = value.get("Value", value) if not value.get("Hidden") else "*" * len(value.get("Value"))

    capabilities_string = json.dumps(capabilities)

    click.secho("\n\tDeploying with following values\n\t===============================", fg="yellow")
    click.echo(f"\tStack name                 : {stack_name}")
    click.echo(f"\tRegion                     : {region}")
    click.echo(f"\tConfirm changeset          : {confirm_changeset}")
    click.echo(f"\tDeployment s3 bucket       : {s3_bucket}")
    click.echo(f"\tCapabilities               : {capabilities_string}")
    click.echo(f"\tParameter overrides        : {_parameters}")

    click.secho("\nInitiating deployment\n=====================", fg="yellow")


def read_config_showcase(template_file):
    _, samconfig = get_config_ctx(template_file)

    status = "Found" if samconfig.exists() else "Not found"
    msg = (
        "Syntax invalid in samconfig.toml; save values "
        "through sam deploy --guided to overwrite file with a valid set of values."
    )
    config_sanity = samconfig.sanity_check()
    click.secho("\nConfiguring SAM deploy\n======================", fg="yellow")
    click.echo(f"\n\tLooking for samconfig.toml :  {status}")
    if samconfig.exists():
        click.echo("\tReading default arguments  :  {}".format("Success" if config_sanity else "Failure"))

    if not config_sanity and samconfig.exists():
        raise GuidedDeployFailedError(msg)


def save_config(template_file, parameter_overrides, **kwargs):

    section = CONFIG_SECTION
    ctx, samconfig = get_config_ctx(template_file)

    cmd_names = get_cmd_names(ctx.info_name, ctx)

    for key, value in kwargs.items():
        if isinstance(value, (list, tuple)):
            value = " ".join(val for val in value)
        if value:
            samconfig.put(cmd_names, section, key, value)

    if parameter_overrides:
        _params = []
        for key, value in parameter_overrides.items():
            if isinstance(value, dict):
                if not value.get("Hidden"):
                    _params.append(f"{key}={value.get('Value')}")
            else:
                _params.append(f"{key}={value}")
        if _params:
            samconfig.put(cmd_names, section, "parameter_overrides", " ".join(_params))

    samconfig.flush()

    click.echo(f"\n\tSaved arguments to config file")
    click.echo("\tRunning 'sam deploy' for future deployments will use the parameters saved above.")
    click.echo("\tThe above parameters can be changed by modifying samconfig.toml")
    click.echo(
        "\tLearn more about samconfig.toml syntax at "
        "\n\thttps://docs.aws.amazon.com/serverless-application-model/latest/"
        "developerguide/serverless-sam-cli-config.html"
    )


def get_config_ctx(template_file):
    ctx = click.get_current_context()

    samconfig_dir = getattr(ctx, "samconfig_dir", None)
    samconfig = SamConfig(
        config_dir=samconfig_dir if samconfig_dir else SamConfig.config_dir(template_file_path=template_file)
    )
    return ctx, samconfig


def sanitize_parameter_overrides(parameter_overrides):
    return {key: value.get("Value") if isinstance(value, dict) else value for key, value in parameter_overrides.items()}
