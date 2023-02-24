"""
InfraSyncExecutor class which runs build, package and deploy contexts
"""
import logging

from boto3 import Session
from typing import Optional, Set

from samcli.commands.build.build_context import BuildContext
from samcli.commands.deploy.deploy_context import DeployContext
from samcli.commands.package.package_context import PackageContext
from samcli.lib.utils.boto_utils import get_boto_client_provider_from_session_with_config

LOG = logging.getLogger(__name__)


class InfraSyncExecutor:
    """
    Executor for infra sync that contains skip logic when template is not changed
    """

    _build_context: BuildContext
    _package_context: PackageContext
    _deploy_context: DeployContext

    def __init__(self, build_context: BuildContext, package_context: PackageContext, deploy_context: DeployContext):
        """Constructs the sync for infra executor.

        Parameters
        ----------
        build_context : BuildContext
            BuildContext
        package_context : PackageContext
            PackageContext
        deploy_context : DeployContext
            DeployContext
        """
        self._build_context = build_context
        self._package_context = package_context
        self._deploy_context = deploy_context

        self._session = Session(profile_name=self._deploy_context.profile, region_name=self._deploy_context.region)
        self._cfn_client = self._boto_client("cloudformation")
        self._s3_client = self._boto_client("s3")

    def _boto_client(self, client_name: str):
        """
        Creates boto client
        Parameters
        ----------
        client_name: str
            The name of the client
        Returns
        -------
        Service client instance
        """
        return get_boto_client_provider_from_session_with_config(self._session)(client_name)

    def execute_infra_sync(self, first_sync: bool = False) -> bool:
        """
        Compares the local template with the deployed one, executes infra sync if different

        Parameters
        ----------
        first_sync: bool
            A flag that signals the inital run, only true when it's the first time running infra sync

        Returns
        -------
        bool
            Returns True if infra sync got executed
            Returns False if infra sync got skipped
        """
        self._build_context.set_up()
        self._build_context.run()
        self._package_context.run()

        # Will not combine the comparisons in order to save operation cost
        if first_sync:
            if self._auto_skip_infra(
                self._package_context.output_template_file,
                self._package_context.template_file,
                self._deploy_context.stack_name,
            ):
                LOG.info("Template haven't been changed since last deployment, skipping infra sync...")
                return False

        self._deploy_context.run()

        return True

    def _auto_skip_infra(self, packaged_template_path: str, built_template_path: str, stack_name: str) -> bool:
        return False
    
    @property
    def code_sync_resources(self) -> Set[str]:
        """Returns the list of resources that should trigger code sync"""
        return self._code_sync_resources
