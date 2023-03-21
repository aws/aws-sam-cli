"""
Contains sync flow implementation for Auto Dependency Layer
"""
import hashlib
import logging
import os
import tempfile
import uuid
from typing import TYPE_CHECKING, Dict, List, Optional, cast

from samcli.lib.bootstrap.nested_stack.nested_stack_builder import NestedStackBuilder
from samcli.lib.bootstrap.nested_stack.nested_stack_manager import NestedStackManager
from samcli.lib.build.app_builder import ApplicationBuildResult
from samcli.lib.build.build_graph import BuildGraph
from samcli.lib.package.utils import make_zip_with_lambda_permissions
from samcli.lib.providers.provider import Function, Stack
from samcli.lib.providers.sam_function_provider import SamFunctionProvider
from samcli.lib.sync.exceptions import (
    InvalidRuntimeDefinitionForFunction,
    MissingFunctionBuildDefinition,
    NoLayerVersionsFoundError,
)
from samcli.lib.sync.flows.layer_sync_flow import AbstractLayerSyncFlow
from samcli.lib.sync.flows.zip_function_sync_flow import ZipFunctionSyncFlow
from samcli.lib.sync.sync_flow import SyncFlow
from samcli.lib.utils.hash import file_checksum

if TYPE_CHECKING:  # pragma: no cover
    from samcli.commands.build.build_context import BuildContext
    from samcli.commands.deploy.deploy_context import DeployContext
    from samcli.commands.sync.sync_context import SyncContext

LOG = logging.getLogger(__name__)


class AutoDependencyLayerSyncFlow(AbstractLayerSyncFlow):
    """
    Auto Dependency Layer, Layer Sync flow.
    It creates auto dependency layer files out of function dependencies, and syncs layer code and then updates
    the function configuration with new layer version

    This flow is not instantiated from factory method, please see AutoDependencyLayerParentSyncFlow
    """

    _function_identifier: str
    _build_graph: Optional[BuildGraph]

    def __init__(
        self,
        function_identifier: str,
        build_graph: BuildGraph,
        build_context: "BuildContext",
        deploy_context: "DeployContext",
        sync_context: "SyncContext",
        physical_id_mapping: Dict[str, str],
        stacks: List[Stack],
        application_build_result: Optional[ApplicationBuildResult],
    ):
        super().__init__(
            NestedStackBuilder.get_layer_logical_id(function_identifier),
            build_context,
            deploy_context,
            sync_context,
            physical_id_mapping,
            stacks,
            application_build_result,
        )
        self._function_identifier = function_identifier
        self._build_graph = build_graph

    def set_up(self) -> None:
        super().set_up()

        # find layer's physical id
        layer_name = NestedStackBuilder.get_layer_name(self._deploy_context.stack_name, self._function_identifier)
        layer_versions = self._lambda_client.list_layer_versions(LayerName=layer_name).get("LayerVersions", [])
        if not layer_versions:
            raise NoLayerVersionsFoundError(layer_name)
        self._layer_arn = layer_versions[0].get("LayerVersionArn").rsplit(":", 1)[0]

    def gather_resources(self) -> None:
        function_build_definitions = cast(BuildGraph, self._build_graph).get_function_build_definitions()
        if not function_build_definitions:
            raise MissingFunctionBuildDefinition(self._function_identifier)

        self._artifact_folder = NestedStackManager.update_layer_folder(
            self._build_context.build_dir,
            function_build_definitions[0].dependencies_dir,
            self._layer_identifier,
            self._function_identifier,
            self._get_compatible_runtimes()[0],
        )
        zip_file_path = os.path.join(tempfile.gettempdir(), "data-" + uuid.uuid4().hex)
        self._zip_file = make_zip_with_lambda_permissions(zip_file_path, self._artifact_folder)
        self._local_sha = file_checksum(cast(str, self._zip_file), hashlib.sha256())

    def _get_dependent_functions(self) -> List[Function]:
        function = SamFunctionProvider(cast(List[Stack], self._stacks)).get(self._function_identifier)
        return [function] if function else []

    def _get_compatible_runtimes(self) -> List[str]:
        function = SamFunctionProvider(cast(List[Stack], self._stacks)).get(self._function_identifier)
        if not function or not function.runtime:
            raise InvalidRuntimeDefinitionForFunction(self._function_identifier)
        return [function.runtime]


class AutoDependencyLayerParentSyncFlow(ZipFunctionSyncFlow):
    """
    Parent sync flow for auto dependency layer

    It builds function with regular ZipFunctionSyncFlow, and then adds _AutoDependencyLayerSyncFlow to start syncing
    dependency layer.
    """

    def gather_dependencies(self) -> List[SyncFlow]:
        """
        Return auto dependency layer sync flow along with parent dependencies
        """
        parent_dependencies = super().gather_dependencies()

        function_build_definitions = cast(BuildGraph, self._build_graph).get_function_build_definitions()
        if not function_build_definitions:
            raise MissingFunctionBuildDefinition(self._function.name)

        # don't queue up auto dependency layer, if dependencies are not changes
        need_dependency_layer_sync = function_build_definitions[0].download_dependencies
        if need_dependency_layer_sync:
            parent_dependencies.append(
                AutoDependencyLayerSyncFlow(
                    self._function_identifier,
                    cast(BuildGraph, self._build_graph),
                    self._build_context,
                    self._deploy_context,
                    self._sync_context,
                    self._physical_id_mapping,
                    cast(List[Stack], self._stacks),
                    self._application_build_result,
                )
            )
        return parent_dependencies

    @staticmethod
    def _combine_dependencies() -> bool:
        return False
