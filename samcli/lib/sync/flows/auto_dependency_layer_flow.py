"""
Contains sync flow implementation for Auto Dependency Layer
"""
import hashlib
import logging
import os
import tempfile
import uuid
from typing import List, TYPE_CHECKING, Dict, cast, Any, Optional

from samcli.lib.bootstrap.nested_stack.nested_stack_builder import NestedStackBuilder
from samcli.lib.bootstrap.nested_stack.nested_stack_manager import NestedStackManager
from samcli.lib.build.build_graph import BuildGraph
from samcli.lib.package.utils import make_zip
from samcli.lib.providers.provider import Function, Stack
from samcli.lib.providers.sam_function_provider import SamFunctionProvider
from samcli.lib.sync.flows.layer_sync_flow import AbstractLayerSyncFlow
from samcli.lib.sync.flows.zip_function_sync_flow import ZipFunctionSyncFlow
from samcli.lib.sync.sync_flow import SyncFlow, ResourceAPICall
from samcli.lib.utils.hash import file_checksum
from samcli.lib.utils.lock_distributor import LockDistributor

if TYPE_CHECKING:
    from samcli.commands.deploy.deploy_context import DeployContext
    from samcli.commands.build.build_context import BuildContext

LOG = logging.getLogger(__name__)


class _AutoDependencyLayerSyncFlow(AbstractLayerSyncFlow):
    """
    Auto Dependency Layer, Layer Sync flow.
    It creates auto dependency layer files out of function dependencies, and syncs layer code and then updates
    the function configuration with new layer version

    This flow is not instantiated from factory method, please see AutoDependencyLayerParentSyncFlow
    """

    _function_identifier: str
    build_graph: Optional[BuildGraph]

    def __init__(
            self,
            function_identifier: str,
            build_context: "BuildContext",
            deploy_context: "DeployContext",
            physical_id_mapping: Dict[str, str],
            stacks: List[Stack],
    ):
        super().__init__(
            NestedStackBuilder.get_layer_logical_id(function_identifier),
            build_context,
            deploy_context,
            physical_id_mapping,
            stacks
        )
        self._function_identifier = function_identifier
        self._layer_physical_name = NestedStackBuilder.get_layer_name(deploy_context.stack_name, function_identifier)
        self.build_graph = None

    def gather_resources(self) -> None:
        function_build_definitions = cast(BuildGraph, self.build_graph).get_function_build_definitions()

        if not function_build_definitions:
            # todo replace with proper exception type
            raise ValueError("Build definition for function cannot be found")

        self._artifact_folder = function_build_definitions[0].dependencies_dir
        NestedStackManager.update_layer_folder(
            self._build_context.build_dir,
            self._artifact_folder,
            self._layer_identifier,
            self._function_identifier,
            self._get_compatible_runtimes()[0]
        )
        zip_file_path = os.path.join(tempfile.gettempdir(), "data-" + uuid.uuid4().hex)
        self._zip_file = make_zip(zip_file_path, self._artifact_folder)
        self._local_sha = file_checksum(cast(str, self._zip_file), hashlib.sha256())

    def _get_dependent_functions(self) -> List[Function]:
        function = SamFunctionProvider(self._stacks).get(self._function_identifier)
        return [function] if function else []

    def _get_compatible_runtimes(self) -> List[str]:
        function_resource = cast(Dict[str, Any], self._get_resource(self._function_identifier))
        return [function_resource.get("Properties", {}).get("Runtime")]


class AutoDependencyLayerParentSyncFlow(SyncFlow):
    """
    Parent sync flow for auto dependency layer

    It first builds function and its dependencies, then it triggers function sync with just function code, and layer
    sync for function's dependencies.

    If function code is changed but dependencies of function is not changed, then layer sync will be skipped.
    If function code is not changed, but its dependencies, then only function sync will be skipped.
    """

    _function_identifier: str
    _layer_identifier: str
    _function_sync_flow: ZipFunctionSyncFlow
    _layer_sync_flow: _AutoDependencyLayerSyncFlow

    def __init__(
            self,
            function_identifier: str,
            build_context: "BuildContext",
            deploy_context: "DeployContext",
            physical_id_mapping: Dict[str, str],
            stacks: List[Stack],
    ):
        super().__init__(
            build_context, deploy_context, physical_id_mapping, f"AutoDepLayer for {function_identifier}", stacks
        )
        self._function_identifier = function_identifier
        self._layer_identifier = NestedStackBuilder.get_layer_logical_id(function_identifier)
        self._layer_sync_flow = _AutoDependencyLayerSyncFlow(
            function_identifier, build_context, deploy_context, physical_id_mapping, stacks
        )
        self._function_sync_flow = ZipFunctionSyncFlow(
            function_identifier, build_context, deploy_context, physical_id_mapping, stacks
        )

    def set_up(self) -> None:
        super().set_up()
        self._layer_sync_flow.set_up()
        self._function_sync_flow.set_up()

    def compare_remote(self) -> bool:
        """
        Always return False, individual comparison is been made in sync method
        """
        return False

    def gather_resources(self) -> None:
        """
        First build function then pass BuildGraph information to layer sync flow, so that it can create layer folder
        out of function's dependencies folder
        """
        self._function_sync_flow.gather_resources()
        self._layer_sync_flow.build_graph = self._function_sync_flow.build_graph
        self._layer_sync_flow.gather_resources()

    def sync(self) -> None:
        """
        Manually check if individual sync needs to be executed by first calling compare_method of individual sync flow
        """
        if not self._function_sync_flow.compare_remote():
            LOG.debug("Function code change is detected, syncing function %s", self._function_identifier)
            self._function_sync_flow.sync()
        if not self._layer_sync_flow.compare_remote():
            LOG.debug("Function dependency change is detected, syncing dependency layer %s", self._layer_identifier)
            self._layer_sync_flow.sync()

    def set_locks_with_distributor(self, distributor: LockDistributor):
        """
        Since this class is wrapper, pass lock distributors to other sync flow instances.
        """
        super().set_locks_with_distributor(distributor)
        self._layer_sync_flow.set_locks_with_distributor(distributor)
        self._function_sync_flow.set_locks_with_distributor(distributor)

    def gather_dependencies(self) -> List[SyncFlow]:
        """
        Return combined dependencies
        """
        return self._function_sync_flow.gather_dependencies() \
               + self._layer_sync_flow.gather_dependencies()

    def _get_resource_api_calls(self) -> List[ResourceAPICall]:
        """
        Return combined resource api calls
        """
        return self._function_sync_flow.resource_calls + [ResourceAPICall(self._layer_identifier, ["Build"])]

    def _equality_keys(self) -> Any:
        """
        Return combined equality keys
        """
        return self._function_identifier + self._layer_identifier
