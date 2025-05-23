"""
CLI command for "deploy" command
"""

import logging
import os

import click

from samcli.cli.cli_config_file import ConfigProvider, configuration_option, save_params_option
from samcli.cli.main import aws_creds_options, common_options, pass_context, print_cmdline_args
from samcli.commands._utils.cdk_support_decorators import unsupported_command_cdk
from samcli.commands._utils.click_mutex import ClickMutex
from samcli.commands._utils.command_exception_handler import command_exception_handler
from samcli.commands._utils.options import (
    capabilities_option,
    force_upload_option,
    guided_deploy_stack_name,
    image_repositories_option,
    image_repository_option,
    kms_key_id_option,
    metadata_option,
    no_progressbar_option,
    notification_arns_option,
    parameter_override_option,
    resolve_image_repos_option,
    resolve_s3_option,
    role_arn_option,
    s3_bucket_option,
    s3_prefix_option,
    signing_profiles_option,
    stack_name_option,
    tags_option,
    template_click_option,
    use_json_option,
)
from samcli.commands.deploy.core.command import DeployCommand
from samcli.commands.deploy.utils import sanitize_parameter_overrides
from samcli.lib.bootstrap.bootstrap import manage_stack, print_managed_s3_bucket_info
from samcli.lib.bootstrap.companion_stack.companion_stack_manager import sync_ecr_stack
from samcli.lib.cli_validation.image_repository_validation import image_repository_validation
from samcli.lib.telemetry.metric import track_command
from samcli.lib.utils import osutils
from samcli.lib.utils.version_checker import check_newer_version

SHORT_HELP = "Deploy an AWS SAM application."


HELP_TEXT = """The sam deploy command creates a Cloudformation Stack and deploys your resources."""

DESCRIPTION = """
  To turn on the guided interactive mode, specify the --guided option. This mode shows you the parameters 
  required for deployment, provides default options, and optionally saves these options in a configuration 
  file in your project directory. When you perform subsequent deployments of your application using sam deploy, 
  the AWS SAM CLI retrieves the required parameters from the configuration file.
  
  Set SAM_CLI_POLL_DELAY Environment Variable with a value of seconds in your shell to configure 
  how often SAM CLI checks the Stack state, which is useful when seeing throttling from CloudFormation.
"""

CONFIG_SECTION = "parameters"
LOG = logging.getLogger(__name__)


@click.command(
    "deploy",
    short_help=SHORT_HELP,
    context_settings={
        "ignore_unknown_options": False,
        "allow_interspersed_args": True,
        "allow_extra_args": True,
        "max_content_width": 120,
    },
    cls=DeployCommand,
    help=HELP_TEXT,
    description=DESCRIPTION,
    requires_credentials=True,
)
@configuration_option(provider=ConfigProvider(section=CONFIG_SECTION))
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
    "Specify this flag to view stack changes before executing the change set.",
)
@click.option(
    "--fail-on-empty-changeset/--no-fail-on-empty-changeset",
    default=True,
    required=False,
    is_flag=True,
    help="Specify whether AWS SAM CLI should return a non-zero exit code if there are no "
    "changes to be made to the stack. Defaults to a non-zero exit code.",
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
    cls=ClickMutex,
    incompatible_params=["on_failure"],
)
@click.option(
    "--on-failure",
    default="ROLLBACK",
    type=click.Choice(["ROLLBACK", "DELETE", "DO_NOTHING"]),
    required=False,
    help="""
    Provide an action to determine what will happen when a stack fails to create. Three actions are available:\n
    - ROLLBACK: This will rollback a stack to a previous known good state.\n
    - DELETE: The stack will rollback to a previous state if one exists, otherwise the stack will be deleted.\n
    - DO_NOTHING: The stack will not rollback or delete, this is the same as disabling rollback.\n
    Default behaviour is ROLLBACK.\n\n
    
    This option is mutually exclusive with --disable-rollback/--no-disable-rollback. You can provide
    --on-failure or --disable-rollback/--no-disable-rollback but not both at the same time.
    """,
    cls=ClickMutex,
    incompatible_params=["disable_rollback", "no_disable_rollback"],
)
@click.option(
    "--max-wait-duration",
    default=60,
    type=int,
    help="Maximum duration in minutes to wait for the deployment to complete.",
)
@stack_name_option(callback=guided_deploy_stack_name)  # pylint: disable=E1120
@s3_bucket_option(disable_callback=True)  # pylint: disable=E1120
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
@save_params_option
@image_repository_validation()
@pass_context
@track_command
@check_newer_version
@print_cmdline_args
@unsupported_command_cdk(alternative_command="cdk deploy")
@command_exception_handler
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
    save_params,
    config_file,
    config_env,
    disable_rollback,
    on_failure,
    max_wait_duration,
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
        on_failure,
        max_wait_duration,
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
    on_failure,
    max_wait_duration,
):
    """
    Implementation of the ``cli`` method
    """
    from samcli.commands.deploy.deploy_context import DeployContext
    from samcli.commands.deploy.exceptions import DeployResolveS3AndS3SetError
    from samcli.commands.deploy.guided_context import GuidedContext
    from samcli.commands.package.package_context import PackageContext

    if guided:
        # Allow for a guided deploy to prompt and save those details.
        guided_context = GuidedContext(
            template_file=template_file,
            stack_name=stack_name,
            s3_bucket=s3_bucket,
            image_repository=image_repository,
            image_repositories=image_repositories,
            resolve_s3=resolve_s3,
            resolve_image_repos=resolve_image_repos,
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
            print_managed_s3_bucket_info(s3_bucket)

        # TODO Refactor resolve-s3 and resolve-image-repos into one place
        # after we figure out how to enable resolve-images-repos in package
        if resolve_image_repos:
            image_repositories = sync_ecr_stack(
                template_file, stack_name, region, s3_bucket, s3_prefix, image_repositories
            )

    with osutils.tempfile_platform_independent() as output_template_file:
        if guided:
            context_param_overrides = sanitize_parameter_overrides(guided_context.guided_parameter_overrides)
        else:
            context_param_overrides = parameter_overrides
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
            parameter_overrides=context_param_overrides,
        ) as package_context:
            package_context.run()

        # 5s of sleep time between stack checks and describe stack events.
        DEFAULT_POLL_DELAY = 5
        try:
            poll_delay = float(os.getenv("SAM_CLI_POLL_DELAY", str(DEFAULT_POLL_DELAY)))
        except ValueError:
            poll_delay = DEFAULT_POLL_DELAY
        if poll_delay <= 0:
            poll_delay = DEFAULT_POLL_DELAY

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
            parameter_overrides=context_param_overrides,
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
            poll_delay=poll_delay,
            on_failure=on_failure,
            max_wait_duration=max_wait_duration,
        ) as deploy_context:
            deploy_context.run()
