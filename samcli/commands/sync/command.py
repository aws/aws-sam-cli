"""CLI command for "sync" command."""
import logging
import os
from typing import TYPE_CHECKING, List, Optional, Set, Tuple

import click

from samcli.cli.cli_config_file import ConfigProvider, configuration_option
from samcli.cli.context import Context
from samcli.cli.main import aws_creds_options, pass_context, print_cmdline_args
from samcli.cli.main import common_options as cli_framework_options
from samcli.commands._utils.cdk_support_decorators import unsupported_command_cdk
from samcli.commands._utils.click_mutex import ClickMutex
from samcli.commands._utils.command_exception_handler import command_exception_handler
from samcli.commands._utils.constants import (
    DEFAULT_BUILD_DIR,
    DEFAULT_BUILD_DIR_WITH_AUTO_DEPENDENCY_LAYER,
    DEFAULT_CACHE_DIR,
)
from samcli.commands._utils.custom_options.replace_help_option import ReplaceHelpSummaryOption
from samcli.commands._utils.option_value_processor import process_image_options
from samcli.commands._utils.options import (
    base_dir_option,
    build_image_option,
    capabilities_option,
    image_repositories_option,
    image_repository_option,
    kms_key_id_option,
    metadata_option,
    notification_arns_option,
    parameter_override_option,
    role_arn_option,
    s3_bucket_option,
    s3_prefix_option,
    stack_name_option,
    tags_option,
    template_option_without_build,
    use_container_build_option,
)
from samcli.commands.build.click_container import ContainerOptions
from samcli.commands.build.command import _get_mode_value_from_envvar
from samcli.commands.sync.core.command import SyncCommand
from samcli.commands.sync.sync_context import SyncContext
from samcli.lib.bootstrap.bootstrap import manage_stack
from samcli.lib.build.bundler import EsbuildBundlerManager
from samcli.lib.cli_validation.image_repository_validation import image_repository_validation
from samcli.lib.providers.provider import (
    ResourceIdentifier,
    get_all_resource_ids,
    get_unique_resource_ids,
)
from samcli.lib.providers.sam_stack_provider import SamLocalStackProvider
from samcli.lib.sync.infra_sync_executor import InfraSyncExecutor, InfraSyncResult
from samcli.lib.sync.sync_flow_executor import SyncFlowExecutor
from samcli.lib.sync.sync_flow_factory import SyncCodeResources, SyncFlowFactory
from samcli.lib.sync.watch_manager import WatchManager
from samcli.lib.telemetry.event import EventTracker, track_long_event
from samcli.lib.telemetry.metric import track_command, track_template_warnings
from samcli.lib.utils.colors import Colored
from samcli.lib.utils.version_checker import check_newer_version
from samcli.lib.warnings.sam_cli_warning import CodeDeployConditionWarning, CodeDeployWarning

if TYPE_CHECKING:  # pragma: no cover
    from samcli.commands.build.build_context import BuildContext
    from samcli.commands.deploy.deploy_context import DeployContext
    from samcli.commands.package.package_context import PackageContext

LOG = logging.getLogger(__name__)

HELP_TEXT = """
  NEW! Sync an AWS SAM Project to AWS.

"""

DESCRIPTION = """
  By default, `$sam sync` runs a full AWS Cloudformation stack update.

  Running `sam sync --watch` with `--code` will provide a way to run just code
  synchronization, speeding up start time skipping template changes.

  Remember to update the deployed stack by running
  without --code for infrastructure changes.

  `$sam sync` also supports nested stacks and nested stack resources.
"""


SYNC_INFO_TEXT = """
The SAM CLI will use the AWS Lambda, Amazon API Gateway, and AWS StepFunctions APIs to upload your code without 
performing a CloudFormation deployment. This will cause drift in your CloudFormation stack. 
**The sync command should only be used against a development stack**.
"""

SYNC_CONFIRMATION_TEXT = """
Confirm that you are synchronizing a development stack.

Enter Y to proceed with the command, or enter N to cancel:
"""


SHORT_HELP = "Sync an AWS SAM project to AWS."

DEFAULT_TEMPLATE_NAME = "template.yaml"
DEFAULT_CAPABILITIES = ("CAPABILITY_NAMED_IAM", "CAPABILITY_AUTO_EXPAND")


# TODO(sriram-mv): Move context settings to be global such as width.
@click.command(
    "sync",
    cls=SyncCommand,
    help=HELP_TEXT,
    short_help=SHORT_HELP,
    description=DESCRIPTION,
    requires_credentials=True,
    context_settings={"max_content_width": 120},
)
@configuration_option(provider=ConfigProvider(section="parameters"))
@template_option_without_build
@click.option(
    "--code",
    is_flag=True,
    help="Sync ONLY code resources. This includes Lambda Functions, API Gateway, and Step Functions.",
    cls=ClickMutex,
)
@click.option(
    "--watch/--no-watch",
    is_flag=True,
    help="Watch local files and automatically sync with cloud.",
    cls=ClickMutex,
)
@click.option(
    "--resource-id",
    multiple=True,
    help="Sync code for all the resources with the ID. To sync a resource within a nested stack, "
    "use the following pattern {ChildStack}/{logicalId}.",
)
@click.option(
    "--resource",
    multiple=True,
    cls=ReplaceHelpSummaryOption,
    type=click.Choice(SyncCodeResources.values(), case_sensitive=True),
    replace_help_option="--resource RESOURCE",
    help=f"Sync code for all resources of the given resource type. Accepted values are {SyncCodeResources.values()}",
)
@click.option(
    "--dependency-layer/--no-dependency-layer",
    default=True,
    is_flag=True,
    help="Separate dependencies of individual function into a Lambda layer for improved performance.",
)
@click.option(
    "--skip-deploy-sync/--no-skip-deploy-sync",
    default=True,
    is_flag=True,
    help="This option will skip the initial infrastructure deployment if it is not required"
    " by comparing the local template with the template deployed in cloud.",
)
@stack_name_option(required=True)  # pylint: disable=E1120
@base_dir_option
@use_container_build_option
@build_image_option(cls=ContainerOptions)
@image_repository_option
@image_repositories_option
@s3_bucket_option(disable_callback=True)  # pylint: disable=E1120
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
@pass_context
@track_command
@track_long_event("SyncUsed", "Start", "SyncUsed", "End")
@image_repository_validation(support_resolve_image_repos=False)
@track_template_warnings([CodeDeployWarning.__name__, CodeDeployConditionWarning.__name__])
@check_newer_version
@print_cmdline_args
@unsupported_command_cdk()
@command_exception_handler
def cli(
    ctx: Context,
    template_file: str,
    code: bool,
    watch: bool,
    resource_id: Optional[List[str]],
    resource: Optional[List[str]],
    dependency_layer: bool,
    skip_deploy_sync: bool,
    stack_name: str,
    base_dir: Optional[str],
    parameter_overrides: dict,
    image_repository: str,
    image_repositories: Optional[List[str]],
    s3_bucket: str,
    s3_prefix: str,
    kms_key_id: str,
    capabilities: Optional[List[str]],
    role_arn: Optional[str],
    notification_arns: Optional[List[str]],
    tags: dict,
    metadata: dict,
    use_container: bool,
    config_file: str,
    config_env: str,
    build_image: Optional[Tuple[str]],
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
        skip_deploy_sync,
        stack_name,
        ctx.region,
        ctx.profile,
        base_dir,
        parameter_overrides,
        mode,
        image_repository,
        image_repositories,
        s3_bucket,
        s3_prefix,
        kms_key_id,
        capabilities,
        role_arn,
        notification_arns,
        tags,
        metadata,
        use_container,
        build_image,
        config_file,
        config_env,
        None,  # TODO: replace with build_in_source once it's added as a click option
    )  # pragma: no cover


def do_cli(
    template_file: str,
    code: bool,
    watch: bool,
    resource_id: Optional[List[str]],
    resource: Optional[List[str]],
    dependency_layer: bool,
    skip_deploy_sync: bool,
    stack_name: str,
    region: str,
    profile: str,
    base_dir: Optional[str],
    parameter_overrides: dict,
    mode: Optional[str],
    image_repository: str,
    image_repositories: Optional[List[str]],
    s3_bucket: str,
    s3_prefix: str,
    kms_key_id: str,
    capabilities: Optional[List[str]],
    role_arn: Optional[str],
    notification_arns: Optional[List[str]],
    tags: dict,
    metadata: dict,
    use_container: bool,
    build_image: Optional[Tuple[str]],
    config_file: str,
    config_env: str,
    build_in_source: Optional[bool],
) -> None:
    """
    Implementation of the ``cli`` method
    """
    from samcli.cli.global_config import GlobalConfig
    from samcli.commands.build.build_context import BuildContext
    from samcli.commands.deploy.deploy_context import DeployContext
    from samcli.commands.package.package_context import PackageContext
    from samcli.lib.utils import osutils

    global_config = GlobalConfig()
    if not global_config.is_accelerate_opt_in_stack(template_file, stack_name):
        if not click.confirm(Colored().yellow(SYNC_INFO_TEXT + SYNC_CONFIRMATION_TEXT), default=True):
            return
        global_config.set_accelerate_opt_in_stack(template_file, stack_name)
    else:
        LOG.info(Colored().color_log(msg=SYNC_INFO_TEXT, color="yellow"), extra=dict(markup=True))

    s3_bucket_name = s3_bucket or manage_stack(profile=profile, region=region)

    if dependency_layer is True:
        dependency_layer = check_enable_dependency_layer(template_file)

    # Note: ADL with use-container is not supported yet. Remove this logic once its supported.
    if use_container and dependency_layer:
        LOG.info(
            "Note: Automatic Dependency Layer is not yet supported with use-container. \
            sam sync will be run without Automatic Dependency Layer."
        )
        dependency_layer = False

    build_dir = DEFAULT_BUILD_DIR_WITH_AUTO_DEPENDENCY_LAYER if dependency_layer else DEFAULT_BUILD_DIR
    LOG.debug("Using build directory as %s", build_dir)
    EventTracker.track_event("UsedFeature", "Accelerate")

    processed_build_images = process_image_options(build_image)

    with BuildContext(
        resource_identifier=None,
        template_file=template_file,
        base_dir=base_dir,
        build_dir=build_dir,
        cache_dir=DEFAULT_CACHE_DIR,
        clean=True,
        use_container=use_container,
        cached=True,
        parallel=True,
        parameter_overrides=parameter_overrides,
        mode=mode,
        create_auto_dependency_layer=dependency_layer,
        stack_name=stack_name,
        print_success_message=False,
        locate_layer_nested=True,
        build_in_source=build_in_source,
        build_images=processed_build_images,
    ) as build_context:
        built_template = os.path.join(build_dir, DEFAULT_TEMPLATE_NAME)

        with osutils.tempfile_platform_independent() as output_template_file:
            with PackageContext(
                template_file=built_template,
                s3_bucket=s3_bucket_name,
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
                # 500ms of sleep time between stack checks and describe stack events.
                DEFAULT_POLL_DELAY = 0.5
                try:
                    poll_delay = float(os.getenv("SAM_CLI_POLL_DELAY", str(DEFAULT_POLL_DELAY)))
                except ValueError:
                    poll_delay = DEFAULT_POLL_DELAY
                if poll_delay <= 0:
                    poll_delay = DEFAULT_POLL_DELAY

                with DeployContext(
                    template_file=output_template_file.name,
                    stack_name=stack_name,
                    s3_bucket=s3_bucket_name,
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
                    poll_delay=poll_delay,
                    on_failure=None,
                ) as deploy_context:
                    with SyncContext(
                        dependency_layer, build_context.build_dir, build_context.cache_dir, skip_deploy_sync
                    ) as sync_context:
                        if watch:
                            execute_watch(
                                template=template_file,
                                build_context=build_context,
                                package_context=package_context,
                                deploy_context=deploy_context,
                                sync_context=sync_context,
                                auto_dependency_layer=dependency_layer,
                                disable_infra_syncs=code,
                            )
                        elif code:
                            execute_code_sync(
                                template=template_file,
                                build_context=build_context,
                                deploy_context=deploy_context,
                                sync_context=sync_context,
                                resource_ids=resource_id,
                                resource_types=resource,
                                auto_dependency_layer=dependency_layer,
                            )
                        else:
                            infra_sync_result = execute_infra_contexts(
                                build_context, package_context, deploy_context, sync_context
                            )
                            code_sync_resources = infra_sync_result.code_sync_resources

                            if not infra_sync_result.infra_sync_executed and code_sync_resources:
                                resource_ids = [str(resource) for resource in code_sync_resources]

                                LOG.info("Queuing up code sync for the resources that require an update")
                                LOG.debug("The following resources will be code synced for an update: %s", resource_ids)
                                execute_code_sync(
                                    template=template_file,
                                    build_context=build_context,
                                    deploy_context=deploy_context,
                                    sync_context=sync_context,
                                    resource_ids=resource_ids,
                                    resource_types=None,
                                    auto_dependency_layer=dependency_layer,
                                    use_built_resources=True,
                                )


def execute_infra_contexts(
    build_context: "BuildContext",
    package_context: "PackageContext",
    deploy_context: "DeployContext",
    sync_context: "SyncContext",
) -> InfraSyncResult:
    """Executes the sync for infra.

    Parameters
    ----------
    build_context : BuildContext
    package_context : PackageContext
    deploy_context : DeployContext
    sync_context : SyncContext

    Returns
    -------
    InfraSyncResult
        Data class that contains infra sync execution result
    """
    infra_sync_executor = InfraSyncExecutor(build_context, package_context, deploy_context, sync_context)
    return infra_sync_executor.execute_infra_sync(first_sync=True)


def execute_code_sync(
    template: str,
    build_context: "BuildContext",
    deploy_context: "DeployContext",
    sync_context: "SyncContext",
    resource_ids: Optional[List[str]],
    resource_types: Optional[List[str]],
    auto_dependency_layer: bool,
    use_built_resources: bool = False,
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
    sync_context: SyncContext
        SyncContext object that obtains sync information.
    resource_ids : List[str]
        List of resource IDs to be synced.
    resource_types : List[str]
        List of resource types to be synced.
    auto_dependency_layer: bool
        Boolean flag to whether enable certain sync flows for auto dependency layer feature
    use_built_resources: bool
        Boolean flag to whether to use pre-build resources from BuildContext or build resources from scratch
    """
    stacks = SamLocalStackProvider.get_stacks(template)[0]
    factory = SyncFlowFactory(build_context, deploy_context, sync_context, stacks, auto_dependency_layer)
    factory.load_physical_id_mapping()
    executor = SyncFlowExecutor()

    sync_flow_resource_ids: Set[ResourceIdentifier] = (
        get_unique_resource_ids(stacks, resource_ids, resource_types)
        if resource_ids or resource_types
        else set(get_all_resource_ids(stacks))
    )

    for resource_id in sync_flow_resource_ids:
        built_result = build_context.build_result if use_built_resources else None
        sync_flow = factory.create_sync_flow(resource_id, built_result)
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
    sync_context: "SyncContext",
    auto_dependency_layer: bool,
    disable_infra_syncs: bool,
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
    sync_context: SyncContext
        SyncContext object that obtains sync information.
    auto_dependency_layer: bool
        Boolean flag to whether enable certain sync flows for auto dependency layer feature.
    disable_infra_syncs: bool
        Boolean flag to determine if sam sync only executes code syncs.
    """
    # Note: disable_infra_syncs  is different from skip_deploy_sync,
    # disable_infra_syncs completely disables infra syncs and
    # skip_deploy_sync skips the initial infra sync if it's not required.
    watch_manager = WatchManager(
        template,
        build_context,
        package_context,
        deploy_context,
        sync_context,
        auto_dependency_layer,
        disable_infra_syncs,
    )
    watch_manager.start()


def check_enable_dependency_layer(template_file: str):
    """
    Check if auto dependency layer should be enabled
    :param template_file: template file string
    :return: True if ADL should be enabled, False otherwise
    """
    stacks, _ = SamLocalStackProvider.get_stacks(template_file)
    for stack in stacks:
        esbuild = EsbuildBundlerManager(stack)
        if esbuild.esbuild_configured():
            # Disable ADL if esbuild is configured. esbuild already makes the package size
            # small enough to ensure that ADL isn't needed to improve performance
            click.secho("esbuild is configured, disabling auto dependency layer.", fg="yellow")
            return False
    return True
