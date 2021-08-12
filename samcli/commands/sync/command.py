"""CLI command for "sync" command."""
import os
import logging
from typing import List, Set, TYPE_CHECKING, Optional, Tuple

import click

from samcli.cli.main import pass_context, common_options as cli_framework_options, aws_creds_options, print_cmdline_args
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
)
from samcli.cli.cli_config_file import configuration_option, TomlProvider
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
from samcli.commands._utils.options import DEFAULT_BUILD_DIR, DEFAULT_CACHE_DIR
from samcli.cli.context import Context
from samcli.lib.sync.watch_manager import WatchManager

if TYPE_CHECKING:
    from samcli.commands.deploy.deploy_context import DeployContext
    from samcli.commands.package.package_context import PackageContext
    from samcli.commands.build.build_context import BuildContext

LOG = logging.getLogger(__name__)

HELP_TEXT = """
Update/sync local artifacts to AWS
"""
SHORT_HELP = "Sync a project to AWS"

DEFAULT_TEMPLATE_NAME = "template.yaml"


@click.command("sync", help=HELP_TEXT, short_help=SHORT_HELP)
@configuration_option(provider=TomlProvider(section="parameters"))
@template_option_without_build
@click.option(
    "--infra",
    is_flag=True,
    help="Sync infrastructure",
)
@click.option(
    "--code",
    is_flag=True,
    help="Sync code resources. This includes Lambda Functions, API Gateway, and Step Functions.",
)
@click.option(
    "--watch",
    is_flag=True,
    help="Watch local files and automatically sync with remote.",
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
@capabilities_option(default=("CAPABILITY_NAMED_IAM", "CAPABILITY_AUTO_EXPAND"))  # pylint: disable=E1120
@pass_context
@track_command
@image_repository_validation
@track_template_warnings([CodeDeployWarning.__name__, CodeDeployConditionWarning.__name__])
@check_newer_version
@print_cmdline_args
def cli(
    ctx: Context,
    template_file: str,
    infra: bool,
    code: bool,
    watch: bool,
    resource_id: Optional[Tuple[str]],
    resource: Optional[Tuple[str]],
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
        infra,
        code,
        watch,
        resource_id,
        resource,
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
    infra: bool,
    code: bool,
    watch: bool,
    resource_id: Optional[Tuple[str]],
    resource: Optional[Tuple[str]],
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
    click.echo("\t\tA different default S3 bucket can be set in samconfig.toml")
    click.echo("\t\tOr by specifying --s3-bucket explicitly.")

    with BuildContext(
        resource_identifier=None,
        template_file=template_file,
        base_dir=base_dir,
        build_dir=DEFAULT_BUILD_DIR,
        cache_dir=DEFAULT_CACHE_DIR,
        clean=True,
        use_container=False,
        cached=True,
        parallel=True,
        parameter_overrides=parameter_overrides,
        mode=mode,
    ) as build_context:
        built_template = os.path.join(".aws-sam", "build", DEFAULT_TEMPLATE_NAME)

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
                ) as deploy_context:
                    if watch:
                        execute_watch(template_file, build_context, package_context, deploy_context)
                    elif code:
                        execute_code_sync(template_file, build_context, deploy_context, resource_id, resource)
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
    """
    stacks = SamLocalStackProvider.get_stacks(template)[0]
    factory = SyncFlowFactory(build_context, deploy_context, stacks)
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
    watch_manager = WatchManager(template, build_context, package_context, deploy_context)
    watch_manager.start()
