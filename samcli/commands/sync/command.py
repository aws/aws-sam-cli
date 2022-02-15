"""CLI command for "sync" command."""
import os
import logging
from typing import List, Set, TYPE_CHECKING, Optional, Tuple

import click

from samcli.cli.main import pass_context, common_options as cli_framework_options, aws_creds_options, print_cmdline_args
from samcli.commands._utils.cdk_support_decorators import unsupported_command_cdk
from samcli.commands._utils.options import (
    template_option_without_build,
    parameter_override_option,
    capabilities_option,
    metadata_option,
    notification_arns_option,
    tags_option,
    stack_name_option,
    base_dir_option,
    image_repository_option,
    image_repositories_option,
    s3_prefix_option,
    kms_key_id_option,
    role_arn_option,
    DEFAULT_BUILD_DIR,
    DEFAULT_CACHE_DIR,
    DEFAULT_BUILD_DIR_WITH_AUTO_DEPENDENCY_LAYER,
)
from samcli.cli.cli_config_file import configuration_option, TomlProvider
from samcli.commands._utils.click_mutex import ClickMutex
from samcli.lib.utils.colors import Colored
from samcli.lib.utils.version_checker import check_newer_version
from samcli.lib.bootstrap.bootstrap import manage_stack
from samcli.lib.cli_validation.image_repository_validation import image_repository_validation
from samcli.lib.telemetry.metric import track_command, track_template_warnings
from samcli.lib.warnings.sam_cli_warning import CodeDeployWarning, CodeDeployConditionWarning
from samcli.commands.build.command import _get_mode_value_from_envvar
from samcli.lib.sync.sync_flow_factory import SyncFlowFactory
from samcli.lib.sync.sync_flow_executor import SyncFlowExecutor
from samcli.lib.providers.sam_stack_provider import SamLocalStackProvider
from samcli.lib.providers.provider import (
    ResourceIdentifier,
    get_all_resource_ids,
    get_unique_resource_ids,
)
from samcli.cli.context import Context
from samcli.lib.sync.watch_manager import WatchManager
from samcli.commands._utils.experimental import (
    ExperimentalFlag,
    experimental,
    is_experimental_enabled,
    set_experimental,
    update_experimental_context,
)

if TYPE_CHECKING:  # pragma: no cover
    from samcli.commands.deploy.deploy_context import DeployContext
    from samcli.commands.package.package_context import PackageContext
    from samcli.commands.build.build_context import BuildContext

LOG = logging.getLogger(__name__)

HELP_TEXT = """
[Beta Feature] Update/Sync local artifacts to AWS

By default, the sync command runs a full stack update. You can specify --code or --watch to switch modes
"""

SYNC_CONFIRMATION_TEXT = """
The SAM CLI will use the AWS Lambda, Amazon API Gateway, and AWS StepFunctions APIs to upload your code without 
performing a CloudFormation deployment. This will cause drift in your CloudFormation stack. 
**The sync command should only be used against a development stack**.
Confirm that you are synchronizing a development stack.

Enter Y to proceed with the command, or enter N to cancel:
"""

SYNC_CONFIRMATION_TEXT_WITH_BETA = """
This feature is currently in beta. Visit the docs page to learn more about the AWS Beta terms https://aws.amazon.com/service-terms/.

The SAM CLI will use the AWS Lambda, Amazon API Gateway, and AWS StepFunctions APIs to upload your code without 
performing a CloudFormation deployment. This will cause drift in your CloudFormation stack. 
**The sync command should only be used against a development stack**.

Confirm that you are synchronizing a development stack and want to turn on beta features.

Enter Y to proceed with the command, or enter N to cancel:
"""


SHORT_HELP = "[Beta Feature] Sync a project to AWS"

DEFAULT_TEMPLATE_NAME = "template.yaml"
DEFAULT_CAPABILITIES = ("CAPABILITY_NAMED_IAM", "CAPABILITY_AUTO_EXPAND")


@click.command("sync", help=HELP_TEXT, short_help=SHORT_HELP)
@configuration_option(provider=TomlProvider(section="parameters"))
@template_option_without_build
@click.option(
    "--code",
    is_flag=True,
    help="Sync code resources. This includes Lambda Functions, API Gateway, and Step Functions.",
    cls=ClickMutex,
    incompatible_params=["watch"],
)
@click.option(
    "--watch",
    is_flag=True,
    help="Watch local files and automatically sync with remote.",
    cls=ClickMutex,
    incompatible_params=["code"],
)
@click.option(
    "--resource-id",
    multiple=True,
    help="Sync code for all the resources with the ID.",
)
@click.option(
    "--resource",
    multiple=True,
    help="Sync code for all types of the resource.",
)
@click.option(
    "--dependency-layer/--no-dependency-layer",
    default=True,
    is_flag=True,
    help="This option separates the dependencies of individual function into another layer, for speeding up the sync"
    "process",
)
@stack_name_option(required=True)  # pylint: disable=E1120
@base_dir_option
@image_repository_option
@image_repositories_option
@s3_prefix_option
@kms_key_id_option
@role_arn_option
@parameter_override_option
@cli_framework_options
@aws_creds_options
@metadata_option
@notification_arns_option
@tags_option
@capabilities_option(default=DEFAULT_CAPABILITIES)  # pylint: disable=E1120
@experimental
@pass_context
@track_command
@image_repository_validation
@track_template_warnings([CodeDeployWarning.__name__, CodeDeployConditionWarning.__name__])
@check_newer_version
@print_cmdline_args
@unsupported_command_cdk()
def cli(
    ctx: Context,
    template_file: str,
    code: bool,
    watch: bool,
    resource_id: Optional[Tuple[str]],
    resource: Optional[Tuple[str]],
    dependency_layer: bool,
    stack_name: str,
    base_dir: Optional[str],
    parameter_overrides: dict,
    image_repository: str,
    image_repositories: Optional[Tuple[str]],
    s3_prefix: str,
    kms_key_id: str,
    capabilities: Optional[List[str]],
    role_arn: Optional[str],
    notification_arns: Optional[List[str]],
    tags: dict,
    metadata: dict,
    config_file: str,
    config_env: str,
) -> None:
    """
    `sam sync` command entry point
    """
    mode = _get_mode_value_from_envvar("SAM_BUILD_MODE", choices=["debug"])
    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing

    do_cli(
        template_file,
        code,
        watch,
        resource_id,
        resource,
        dependency_layer,
        stack_name,
        ctx.region,
        ctx.profile,
        base_dir,
        parameter_overrides,
        mode,
        image_repository,
        image_repositories,
        s3_prefix,
        kms_key_id,
        capabilities,
        role_arn,
        notification_arns,
        tags,
        metadata,
        config_file,
        config_env,
    )  # pragma: no cover


def do_cli(
    template_file: str,
    code: bool,
    watch: bool,
    resource_id: Optional[Tuple[str]],
    resource: Optional[Tuple[str]],
    dependency_layer: bool,
    stack_name: str,
    region: str,
    profile: str,
    base_dir: Optional[str],
    parameter_overrides: dict,
    mode: Optional[str],
    image_repository: str,
    image_repositories: Optional[Tuple[str]],
    s3_prefix: str,
    kms_key_id: str,
    capabilities: Optional[List[str]],
    role_arn: Optional[str],
    notification_arns: Optional[List[str]],
    tags: dict,
    metadata: dict,
    config_file: str,
    config_env: str,
) -> None:
    """
    Implementation of the ``cli`` method
    """
    from samcli.lib.utils import osutils
    from samcli.commands.build.build_context import BuildContext
    from samcli.commands.package.package_context import PackageContext
    from samcli.commands.deploy.deploy_context import DeployContext

    s3_bucket = manage_stack(profile=profile, region=region)
    click.echo(f"\n\t\tManaged S3 bucket: {s3_bucket}")

    click.echo(f"\n\t\tDefault capabilities applied: {DEFAULT_CAPABILITIES}")
    click.echo("To override with customized capabilities, use --capabilities flag or set it in samconfig.toml")

    build_dir = DEFAULT_BUILD_DIR_WITH_AUTO_DEPENDENCY_LAYER if dependency_layer else DEFAULT_BUILD_DIR
    LOG.debug("Using build directory as %s", build_dir)

    build_dir = DEFAULT_BUILD_DIR_WITH_AUTO_DEPENDENCY_LAYER if dependency_layer else DEFAULT_BUILD_DIR
    LOG.debug("Using build directory as %s", build_dir)

    confirmation_text = SYNC_CONFIRMATION_TEXT

    if not is_experimental_enabled(ExperimentalFlag.Accelerate):
        confirmation_text = SYNC_CONFIRMATION_TEXT_WITH_BETA

    if not click.confirm(Colored().yellow(confirmation_text), default=False):
        return

    set_experimental(ExperimentalFlag.Accelerate)
    update_experimental_context()

    with BuildContext(
        resource_identifier=None,
        template_file=template_file,
        base_dir=base_dir,
        build_dir=build_dir,
        cache_dir=DEFAULT_CACHE_DIR,
        clean=True,
        use_container=False,
        cached=True,
        parallel=True,
        parameter_overrides=parameter_overrides,
        mode=mode,
        create_auto_dependency_layer=dependency_layer,
        stack_name=stack_name,
        print_success_message=False,
    ) as build_context:
        built_template = os.path.join(build_dir, DEFAULT_TEMPLATE_NAME)

        with osutils.tempfile_platform_independent() as output_template_file:
            with PackageContext(
                template_file=built_template,
                s3_bucket=s3_bucket,
                image_repository=image_repository,
                image_repositories=image_repositories,
                s3_prefix=s3_prefix,
                kms_key_id=kms_key_id,
                output_template_file=output_template_file.name,
                no_progressbar=True,
                metadata=metadata,
                region=region,
                profile=profile,
                use_json=False,
                force_upload=True,
            ) as package_context:

                with DeployContext(
                    template_file=output_template_file.name,
                    stack_name=stack_name,
                    s3_bucket=s3_bucket,
                    image_repository=image_repository,
                    image_repositories=image_repositories,
                    no_progressbar=True,
                    s3_prefix=s3_prefix,
                    kms_key_id=kms_key_id,
                    parameter_overrides=parameter_overrides,
                    capabilities=capabilities,
                    role_arn=role_arn,
                    notification_arns=notification_arns,
                    tags=tags,
                    region=region,
                    profile=profile,
                    no_execute_changeset=True,
                    fail_on_empty_changeset=True,
                    confirm_changeset=False,
                    use_changeset=False,
                    force_upload=True,
                    signing_profiles=None,
                    disable_rollback=False,
                ) as deploy_context:
                    if watch:
                        execute_watch(template_file, build_context, package_context, deploy_context, dependency_layer)
                    elif code:
                        execute_code_sync(
                            template_file, build_context, deploy_context, resource_id, resource, dependency_layer
                        )
                    else:
                        execute_infra_contexts(build_context, package_context, deploy_context)


def execute_infra_contexts(
    build_context: "BuildContext",
    package_context: "PackageContext",
    deploy_context: "DeployContext",
) -> None:
    """Executes the sync for infra.

    Parameters
    ----------
    build_context : BuildContext
        BuildContext
    package_context : PackageContext
        PackageContext
    deploy_context : DeployContext
        DeployContext
    """
    LOG.debug("Executing the build using build context.")
    build_context.run()
    LOG.debug("Executing the packaging using package context.")
    package_context.run()
    LOG.debug("Executing the deployment using deploy context.")
    deploy_context.run()


def execute_code_sync(
    template: str,
    build_context: "BuildContext",
    deploy_context: "DeployContext",
    resource_ids: Optional[Tuple[str]],
    resource_types: Optional[Tuple[str]],
    auto_dependency_layer: bool,
) -> None:
    """Executes the sync flow for code.

    Parameters
    ----------
    template : str
        Template file name
    build_context : BuildContext
        BuildContext
    deploy_context : DeployContext
        DeployContext
    resource_ids : List[str]
        List of resource IDs to be synced.
    resource_types : List[str]
        List of resource types to be synced.
    auto_dependency_layer: bool
        Boolean flag to whether enable certain sync flows for auto dependency layer feature
    """
    stacks = SamLocalStackProvider.get_stacks(template)[0]
    factory = SyncFlowFactory(build_context, deploy_context, stacks, auto_dependency_layer)
    factory.load_physical_id_mapping()
    executor = SyncFlowExecutor()

    sync_flow_resource_ids: Set[ResourceIdentifier] = (
        get_unique_resource_ids(stacks, resource_ids, resource_types)
        if resource_ids or resource_types
        else set(get_all_resource_ids(stacks))
    )

    for resource_id in sync_flow_resource_ids:
        sync_flow = factory.create_sync_flow(resource_id)
        if sync_flow:
            executor.add_sync_flow(sync_flow)
        else:
            LOG.warning("Cannot create SyncFlow for %s. Skipping.", resource_id)
    executor.execute()


def execute_watch(
    template: str,
    build_context: "BuildContext",
    package_context: "PackageContext",
    deploy_context: "DeployContext",
    auto_dependency_layer: bool,
):
    """Start sync watch execution

    Parameters
    ----------
    template : str
        Template file path
    build_context : BuildContext
        BuildContext
    package_context : PackageContext
        PackageContext
    deploy_context : DeployContext
        DeployContext
    """
    watch_manager = WatchManager(template, build_context, package_context, deploy_context, auto_dependency_layer)
    watch_manager.start()
