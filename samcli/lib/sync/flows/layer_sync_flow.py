"""SyncFlow for Layers"""
import base64
import hashlib
import logging
import os
import re
import shutil
import tempfile
import uuid
from abc import ABC, abstractmethod
from contextlib import ExitStack
from typing import TYPE_CHECKING, Any, Dict, List, Optional, cast

from samcli.lib.build.app_builder import ApplicationBuilder, ApplicationBuildResult
from samcli.lib.package.utils import make_zip_with_lambda_permissions
from samcli.lib.providers.provider import Function, LayerVersion, ResourceIdentifier, Stack, get_resource_by_id
from samcli.lib.providers.sam_function_provider import SamFunctionProvider
from samcli.lib.sync.exceptions import MissingPhysicalResourceError, NoLayerVersionsFoundError
from samcli.lib.sync.flows.function_sync_flow import wait_for_function_update_complete
from samcli.lib.sync.sync_flow import ApiCallTypes, ResourceAPICall, SyncFlow
from samcli.lib.sync.sync_flow_executor import HELP_TEXT_FOR_SYNC_INFRA
from samcli.lib.utils.colors import Colored
from samcli.lib.utils.hash import file_checksum, str_checksum
from samcli.lib.utils.osutils import rmtree_if_exists

if TYPE_CHECKING:  # pragma: no cover
    from samcli.commands.build.build_context import BuildContext
    from samcli.commands.deploy.deploy_context import DeployContext
    from samcli.commands.sync.sync_context import SyncContext

LOG = logging.getLogger(__name__)
FUNCTION_SLEEP = 1  # used to wait for lambda function configuration last update to be successful


def get_latest_layer_version(lambda_client: Any, layer_arn: str) -> int:
    """Fetches all layer versions from remote and returns the latest one"""
    layer_versions = lambda_client.list_layer_versions(LayerName=layer_arn).get("LayerVersions", [])
    if not layer_versions:
        raise NoLayerVersionsFoundError(layer_arn)
    return cast(int, layer_versions[0].get("Version"))


class AbstractLayerSyncFlow(SyncFlow, ABC):
    """
    AbstractLayerSyncFlow contains common operations for a Layer sync.
    """

    _lambda_client: Any
    _layer_arn: Optional[str]
    _old_layer_version: Optional[int]
    _new_layer_version: Optional[int]
    _layer_identifier: str
    _artifact_folder: Optional[str]
    _zip_file: Optional[str]

    def __init__(
        self,
        layer_identifier: str,
        build_context: "BuildContext",
        deploy_context: "DeployContext",
        sync_context: "SyncContext",
        physical_id_mapping: Dict[str, str],
        stacks: List[Stack],
        application_build_result: Optional[ApplicationBuildResult],
    ):
        super().__init__(
            build_context,
            deploy_context,
            sync_context,
            physical_id_mapping,
            f"Layer {layer_identifier}",
            stacks,
            application_build_result,
        )
        self._layer_identifier = layer_identifier
        self._layer_arn = None
        self._old_layer_version = None
        self._new_layer_version = None
        self._zip_file = None
        self._artifact_folder = None

    def set_up(self) -> None:
        super().set_up()
        self._lambda_client = self._boto_client("lambda")

    @property
    def sync_state_identifier(self) -> str:
        """
        Sync state is the unique identifier for each sync flow
        In sync state toml file we will store
        Key as LayerSyncFlow:LayerLogicalId
        Value as layer ZIP hash
        """
        return self.__class__.__name__ + ":" + self._layer_identifier

    def compare_remote(self) -> bool:
        """
        Compare Sha256 of the deployed layer code vs the one just built, True if they are same, False otherwise
        """
        self._old_layer_version = get_latest_layer_version(self._lambda_client, cast(str, self._layer_arn))
        old_layer_info = self._lambda_client.get_layer_version(
            LayerName=self._layer_arn,
            VersionNumber=self._old_layer_version,
        )
        remote_sha = base64.b64decode(old_layer_info.get("Content", {}).get("CodeSha256", "")).hex()
        LOG.debug("%sLocal SHA: %s Remote SHA: %s", self.log_prefix, self._local_sha, remote_sha)

        return self._local_sha == remote_sha

    def sync(self) -> None:
        """
        Publish new layer version, and delete the existing (old) one
        """
        LOG.debug("%sPublishing new Layer Version", self.log_prefix)
        self._new_layer_version = self._publish_new_layer_version()
        self._delete_old_layer_version()

    def gather_dependencies(self) -> List[SyncFlow]:
        if self._zip_file and os.path.exists(self._zip_file):
            os.remove(self._zip_file)

        dependencies: List[SyncFlow] = list()
        dependent_functions = self._get_dependent_functions()
        if self._stacks:
            for function in dependent_functions:
                dependencies.append(
                    FunctionLayerReferenceSync(
                        function.full_path,
                        cast(str, self._layer_arn),
                        cast(int, self._new_layer_version),
                        self._build_context,
                        self._deploy_context,
                        self._sync_context,
                        self._physical_id_mapping,
                        self._stacks,
                    )
                )
        return dependencies

    def _get_resource_api_calls(self) -> List[ResourceAPICall]:
        return [ResourceAPICall(self._layer_identifier, [ApiCallTypes.BUILD])]

    def _equality_keys(self) -> Any:
        return self._layer_identifier

    def _publish_new_layer_version(self) -> int:
        """
        Publish new layer version and keep new layer version arn so that we can update related functions
        """
        compatible_runtimes = self._get_compatible_runtimes()
        with open(cast(str, self._zip_file), "rb") as zip_file:
            data = zip_file.read()
            layer_publish_result = self._lambda_client.publish_layer_version(
                LayerName=self._layer_arn, Content={"ZipFile": data}, CompatibleRuntimes=compatible_runtimes
            )
            LOG.debug("%sPublish Layer Version Result %s", self.log_prefix, layer_publish_result)
            return int(layer_publish_result.get("Version"))

    def _delete_old_layer_version(self) -> None:
        """
        Delete old layer version for not hitting the layer version limit
        """
        LOG.debug(
            "%sDeleting old Layer Version %s:%s", self.log_prefix, self._old_layer_version, self._old_layer_version
        )
        delete_layer_version_result = self._lambda_client.delete_layer_version(
            LayerName=self._layer_arn,
            VersionNumber=self._old_layer_version,
        )
        LOG.debug("%sDelete Layer Version Result %s", self.log_prefix, delete_layer_version_result)

    @abstractmethod
    def _get_compatible_runtimes(self) -> List[str]:
        """
        Returns compatible runtimes of the Layer instance that is going to be synced

        Returns
        -------
        List[str]
            List of strings which identifies the compatible runtimes for this layer
        """
        raise NotImplementedError("_get_compatible_runtimes not implemented")

    @abstractmethod
    def _get_dependent_functions(self) -> List[Function]:
        """
        Returns list of Function instances, which is depending on this Layer. This information is used to setup
        dependency sync flows, which will update each function's configuration with new layer version.

        Returns
        -------
        List[Function]
            List of Function instances which uses this Layer
        """
        raise NotImplementedError("_get_dependent_functions not implemented")


class LayerSyncFlow(AbstractLayerSyncFlow):
    """SyncFlow for Lambda Layers"""

    _new_layer_version: Optional[int]
    _layer: LayerVersion

    def __init__(
        self,
        layer_identifier: str,
        build_context: "BuildContext",
        deploy_context: "DeployContext",
        sync_context: "SyncContext",
        physical_id_mapping: Dict[str, str],
        stacks: List[Stack],
        application_build_result: Optional[ApplicationBuildResult],
    ):
        super().__init__(
            layer_identifier,
            build_context,
            deploy_context,
            sync_context,
            physical_id_mapping,
            stacks,
            application_build_result,
        )
        self._layer = cast(LayerVersion, build_context.layer_provider.get(self._layer_identifier))

    def set_up(self) -> None:
        super().set_up()

        # if layer is a serverless layer, its physical id contains hashes, try to find layer resource
        if self._layer_identifier not in self._physical_id_mapping:
            expression = re.compile(f"^{self._layer_identifier}[0-9a-z]{{10}}$")
            for logical_id, _ in self._physical_id_mapping.items():
                # Skip over resources that do exist in the template as generated LayerVersion should not be in there
                if get_resource_by_id(cast(List[Stack], self._stacks), ResourceIdentifier(logical_id), True):
                    continue
                # Check if logical ID starts with serverless layer and has 10 characters behind
                if not expression.match(logical_id):
                    continue

                self._layer_arn = self.get_physical_id(logical_id).rsplit(":", 1)[0]
                LOG.debug("%sLayer physical name has been set to %s", self.log_prefix, self._layer_identifier)
                break
            else:
                raise MissingPhysicalResourceError(
                    self._layer_identifier,
                    self._physical_id_mapping,
                )
        else:
            self._layer_arn = self.get_physical_id(self._layer_identifier).rsplit(":", 1)[0]
            LOG.debug("%sLayer physical name has been set to %s", self.log_prefix, self._layer_identifier)

    def gather_resources(self) -> None:
        """Build layer and ZIP it into a temp file in self._zip_file"""
        if self._application_build_result:
            LOG.debug("Using pre-built resources for layer {}", self._layer_identifier)
            self._use_prebuilt_resources(self._application_build_result)
        else:
            LOG.debug("Building layer from scratch {}", self._layer_identifier)
            self._build_resources_from_scratch()

        zip_file_path = os.path.join(tempfile.gettempdir(), f"data-{uuid.uuid4().hex}")
        self._zip_file = make_zip_with_lambda_permissions(zip_file_path, self._artifact_folder)
        LOG.debug("%sCreated artifact ZIP file: %s", self.log_prefix, self._zip_file)
        self._local_sha = file_checksum(cast(str, self._zip_file), hashlib.sha256())

    def _use_prebuilt_resources(self, application_build_result: ApplicationBuildResult) -> None:
        """Uses pre-build artifacts and assigns artifact_folder"""
        self._artifact_folder = application_build_result.artifacts.get(self._layer_identifier)

    def _build_resources_from_scratch(self) -> None:
        """Builds layer from scratch and assigns artifact_folder"""
        with self._get_lock_chain():
            rmtree_if_exists(self._layer.get_build_dir(self._build_context.build_dir))
            builder = ApplicationBuilder(
                self._build_context.collect_build_resources(self._layer_identifier),
                self._build_context.build_dir,
                self._build_context.base_dir,
                self._build_context.cache_dir,
                cached=True,
                is_building_specific_resource=True,
                manifest_path_override=self._build_context.manifest_path_override,
                container_manager=self._build_context.container_manager,
                mode=self._build_context.mode,
                build_in_source=self._build_context.build_in_source,
            )
            LOG.debug("%sBuilding Layer", self.log_prefix)
            self._artifact_folder = builder.build().artifacts.get(self._layer_identifier)

    def _get_compatible_runtimes(self):
        layer_resource = cast(Dict[str, Any], self._get_resource(self._layer_identifier))
        return layer_resource.get("Properties", {}).get("CompatibleRuntimes", [])

    def _get_dependent_functions(self) -> List[Function]:
        function_provider = SamFunctionProvider(cast(List[Stack], self._stacks), locate_layer_nested=True)

        dependent_functions = []
        for function in function_provider.get_all():
            if self._layer_identifier in [layer.full_path for layer in function.layers]:
                LOG.debug(
                    "%sAdding function %s for updating its Layers with this new version",
                    self.log_prefix,
                    function.name,
                )
                dependent_functions.append(function)
        return dependent_functions


class LayerSyncFlowSkipBuildDirectory(LayerSyncFlow):
    """
    LayerSyncFlow special implementation that will skip build step and zip contents of CodeUri
    """

    def gather_resources(self) -> None:
        zip_file_path = os.path.join(tempfile.gettempdir(), f"data-{uuid.uuid4().hex}")
        self._zip_file = make_zip_with_lambda_permissions(zip_file_path, self._layer.codeuri)
        LOG.debug("%sCreated artifact ZIP file: %s", self.log_prefix, self._zip_file)
        self._local_sha = file_checksum(cast(str, self._zip_file), hashlib.sha256())


class LayerSyncFlowSkipBuildZipFile(LayerSyncFlow):
    """
    LayerSyncFlow special implementation, that will skip build and upload zip file which is defined in CodeUri directly
    """

    def gather_resources(self) -> None:
        self._zip_file = os.path.join(tempfile.gettempdir(), f"data-{uuid.uuid4().hex}")
        shutil.copy2(cast(str, self._layer.codeuri), self._zip_file)
        LOG.debug("%sCreated artifact ZIP file: %s", self.log_prefix, self._zip_file)
        self._local_sha = file_checksum(self._zip_file, hashlib.sha256())


class FunctionLayerReferenceSync(SyncFlow):
    """
    Used for updating new Layer version for the related functions
    """

    _lambda_client: Any

    _function_identifier: str
    _layer_arn: str
    _old_layer_version: int
    _new_layer_version: Optional[int]

    def __init__(
        self,
        function_identifier: str,
        layer_arn: str,
        new_layer_version: Optional[int],
        build_context: "BuildContext",
        deploy_context: "DeployContext",
        sync_context: "SyncContext",
        physical_id_mapping: Dict[str, str],
        stacks: List[Stack],
    ):
        super().__init__(
            build_context,
            deploy_context,
            sync_context,
            physical_id_mapping,
            log_name="Function Layer Reference Sync " + function_identifier,
            stacks=stacks,
        )
        self._function_identifier = function_identifier
        self._layer_arn = layer_arn
        self._new_layer_version = new_layer_version
        self._color = Colored()

    @property
    def sync_state_identifier(self) -> str:
        """
        Sync state is the unique identifier for each sync flow
        In sync state toml file we will store
        Key as FunctionLayerReferenceSync:FunctionLogicalId:LayerArn
        Value as LayerVersion hash
        """
        return self.__class__.__name__ + ":" + self._function_identifier + ":" + self._layer_arn

    def set_up(self) -> None:
        super().set_up()
        self._lambda_client = self._boto_client("lambda")

    def gather_resources(self) -> None:
        if not self._new_layer_version:
            LOG.debug("No layer version set for %s, fetching latest one", self._layer_arn)
            self._new_layer_version = get_latest_layer_version(self._lambda_client, self._layer_arn)
        self._local_sha = str_checksum(str(self._new_layer_version), hashlib.sha256())

    def sync(self) -> None:
        """
        First read the current Layers property and update the old layer version arn with new one
        then call the update function configuration to update the function with new layer version arn
        """
        new_layer_arn = f"{self._layer_arn}:{self._new_layer_version}"

        function_physical_id = self.get_physical_id(self._function_identifier)
        get_function_result = self._lambda_client.get_function(FunctionName=function_physical_id)

        # get the current layer version arns
        layer_arns = [layer.get("Arn") for layer in get_function_result.get("Configuration", {}).get("Layers", [])]

        # Check whether layer version is up to date
        if new_layer_arn in layer_arns:
            LOG.warning(
                "%sLambda Function (%s) is already up to date with new Layer version (%d).",
                self.log_prefix,
                self._function_identifier,
                self._new_layer_version,
            )
            return

        # Check function uses layer
        old_layer_arn = [layer_arn for layer_arn in layer_arns if layer_arn.startswith(self._layer_arn)]
        old_layer_arn = old_layer_arn[0] if len(old_layer_arn) == 1 else None
        if not old_layer_arn:
            LOG.warning(
                "%sLambda Function (%s) does not have layer (%s).%s",
                self.log_prefix,
                self._function_identifier,
                self._layer_arn,
                HELP_TEXT_FOR_SYNC_INFRA,
            )
            return

        # remove the old layer version arn and add the new one
        layer_arns.remove(old_layer_arn)
        layer_arns.append(new_layer_arn)

        with ExitStack() as exit_stack:
            if self.has_locks():
                exit_stack.enter_context(self._get_lock_chain())

            self._lambda_client.update_function_configuration(FunctionName=function_physical_id, Layers=layer_arns)

            # We need to wait for the cloud side update to finish
            # Otherwise even if the call is finished and lockchain is released
            # It is still possible that we have a race condition on cloud updating the same function
            wait_for_function_update_complete(self._lambda_client, self.get_physical_id(self._function_identifier))

    def _get_resource_api_calls(self) -> List[ResourceAPICall]:
        # We need to acquire lock for both API calls since they would conflict on cloud
        # Any UPDATE_FUNCTION_CODE and UPDATE_FUNCTION_CONFIGURATION on the same function
        # Cannot take place in parallel
        return [
            ResourceAPICall(
                self._function_identifier,
                [ApiCallTypes.UPDATE_FUNCTION_CODE, ApiCallTypes.UPDATE_FUNCTION_CONFIGURATION],
            )
        ]

    def compare_remote(self) -> bool:
        return False

    def gather_dependencies(self) -> List["SyncFlow"]:
        return []

    def _equality_keys(self) -> Any:
        return self._function_identifier, self._layer_arn, self._new_layer_version
