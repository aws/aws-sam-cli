"""
CLI command for "deploy" command
"""
import logging

import click

from samcli.cli.cli_config_file import TomlProvider, configuration_option
from samcli.cli.main import aws_creds_options, common_options, pass_context, print_cmdline_args
from samcli.commands._utils.cdk_support_decorators import unsupported_command_cdk
from samcli.commands._utils.options import (
    capabilities_option,
    guided_deploy_stack_name,
    metadata_option,
    notification_arns_option,
    parameter_override_option,
    no_progressbar_option,
    tags_option,
    template_click_option,
    signing_profiles_option,
    stack_name_option,
    s3_bucket_option,
    image_repository_option,
    image_repositories_option,
    s3_prefix_option,
    kms_key_id_option,
    use_json_option,
    force_upload_option,
    resolve_s3_option,
    role_arn_option,
    resolve_image_repos_option,
)
from samcli.commands.deploy.utils import sanitize_parameter_overrides
from samcli.lib.telemetry.metric import track_command
from samcli.lib.cli_validation.image_repository_validation import image_repository_validation
from samcli.lib.utils import osutils
from samcli.lib.bootstrap.bootstrap import manage_stack
from samcli.lib.utils.version_checker import check_newer_version
from samcli.lib.bootstrap.companion_stack.companion_stack_manager import sync_ecr_stack

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
    "--disable-rollback/--no-disable-rollback",
    default=False,
    required=False,
    is_flag=True,
    help="Preserves the state of previously provisioned resources when an operation fails.",
)
@stack_name_option(callback=guided_deploy_stack_name)  # pylint: disable=E1120
@s3_bucket_option(guided=True)  # pylint: disable=E1120
@image_repository_option
@image_repositories_option
@force_upload_option
@s3_prefix_option
@kms_key_id_option
@role_arn_option
@use_json_option
@resolve_s3_option(guided=True)  # pylint: disable=E1120
@resolve_image_repos_option
@metadata_option
@notification_arns_option
@tags_option
@parameter_override_option
@signing_profiles_option
@no_progressbar_option
@capabilities_option
@aws_creds_options
@common_options
@image_repository_validation
@pass_context
@track_command
@check_newer_version
@print_cmdline_args
@unsupported_command_cdk(alternative_command="cdk deploy")
def cli(
    ctx,
    template_file,
    stack_name,
    s3_bucket,
    image_repository,
    image_repositories,
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
    signing_profiles,
    resolve_s3,
    resolve_image_repos,
    config_file,
    config_env,
    disable_rollback,
):
    """
    `sam deploy` command entry point
    """
    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing
    do_cli(
        template_file,
        stack_name,
        s3_bucket,
        image_repository,
        image_repositories,
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
        signing_profiles,
        resolve_s3,
        config_file,
        config_env,
        resolve_image_repos,
        disable_rollback,
    )  # pragma: no cover


def do_cli(
    template_file,
    stack_name,
    s3_bucket,
    image_repository,
    image_repositories,
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
    signing_profiles,
    resolve_s3,
    config_file,
    config_env,
    resolve_image_repos,
    disable_rollback,
):
    """
    Implementation of the ``cli`` method
    """
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
            image_repository=image_repository,
            image_repositories=image_repositories,
            s3_prefix=s3_prefix,
            region=region,
            profile=profile,
            confirm_changeset=confirm_changeset,
            capabilities=capabilities,
            signing_profiles=signing_profiles,
            parameter_overrides=parameter_overrides,
            config_section=CONFIG_SECTION,
            config_env=config_env,
            config_file=config_file,
            disable_rollback=disable_rollback,
        )
        guided_context.run()
    else:
        if resolve_s3:
            if bool(s3_bucket):
                raise DeployResolveS3AndS3SetError()
            s3_bucket = manage_stack(profile=profile, region=region)
            click.echo(f"\n\t\tManaged S3 bucket: {s3_bucket}")
            click.echo("\t\tA different default S3 bucket can be set in samconfig.toml")
            click.echo("\t\tOr by specifying --s3-bucket explicitly.")

        # TODO Refactor resolve-s3 and resolve-image-repos into one place
        # after we figure out how to enable resolve-images-repos in package
        if resolve_image_repos:
            image_repositories = sync_ecr_stack(
                template_file, stack_name, region, s3_bucket, s3_prefix, image_repositories
            )

    with osutils.tempfile_platform_independent() as output_template_file:

        with PackageContext(
            template_file=template_file,
            s3_bucket=guided_context.guided_s3_bucket if guided else s3_bucket,
            s3_prefix=guided_context.guided_s3_prefix if guided else s3_prefix,
            image_repository=guided_context.guided_image_repository if guided else image_repository,
            image_repositories=guided_context.guided_image_repositories if guided else image_repositories,
            output_template_file=output_template_file.name,
            kms_key_id=kms_key_id,
            use_json=use_json,
            force_upload=force_upload,
            no_progressbar=no_progressbar,
            metadata=metadata,
            on_deploy=True,
            region=guided_context.guided_region if guided else region,
            profile=profile,
            signing_profiles=guided_context.signing_profiles if guided else signing_profiles,
        ) as package_context:
            package_context.run()

        with DeployContext(
            template_file=output_template_file.name,
            stack_name=guided_context.guided_stack_name if guided else stack_name,
            s3_bucket=guided_context.guided_s3_bucket if guided else s3_bucket,
            image_repository=guided_context.guided_image_repository if guided else image_repository,
            image_repositories=guided_context.guided_image_repositories if guided else image_repositories,
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
            signing_profiles=guided_context.signing_profiles if guided else signing_profiles,
            use_changeset=True,
            disable_rollback=guided_context.disable_rollback if guided else disable_rollback,
        ) as deploy_context:
            deploy_context.run()
