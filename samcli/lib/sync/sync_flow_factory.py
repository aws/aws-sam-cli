"""SyncFlow Factory for creating SyncFlows based on resource types"""

import logging
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, cast

from botocore.exceptions import ClientError

from samcli.commands.build.build_context import BuildContext
from samcli.commands.exceptions import InvalidStackNameException
from samcli.lib.bootstrap.nested_stack.nested_stack_manager import NestedStackManager
from samcli.lib.build.app_builder import ApplicationBuildResult
from samcli.lib.package.utils import is_local_folder, is_zip_file
from samcli.lib.providers.provider import Function, FunctionBuildInfo, ResourceIdentifier, Stack
from samcli.lib.sync.flows.auto_dependency_layer_sync_flow import AutoDependencyLayerParentSyncFlow
from samcli.lib.sync.flows.function_sync_flow import FunctionSyncFlow
from samcli.lib.sync.flows.http_api_sync_flow import HttpApiSyncFlow
from samcli.lib.sync.flows.image_function_sync_flow import ImageFunctionSyncFlow
from samcli.lib.sync.flows.layer_sync_flow import (
    LayerSyncFlow,
    LayerSyncFlowSkipBuildDirectory,
    LayerSyncFlowSkipBuildZipFile,
)
from samcli.lib.sync.flows.rest_api_sync_flow import RestApiSyncFlow
from samcli.lib.sync.flows.stepfunctions_sync_flow import StepFunctionsSyncFlow
from samcli.lib.sync.flows.zip_function_sync_flow import (
    ZipFunctionSyncFlow,
    ZipFunctionSyncFlowSkipBuildDirectory,
    ZipFunctionSyncFlowSkipBuildZipFile,
)
from samcli.lib.sync.sync_flow import SyncFlow
from samcli.lib.utils.boto_utils import (
    get_boto_client_provider_with_config,
    get_boto_resource_provider_with_config,
    get_client_error_code,
)
from samcli.lib.utils.cloudformation import get_resource_summaries
from samcli.lib.utils.packagetype import IMAGE, ZIP
from samcli.lib.utils.resource_type_based_factory import ResourceTypeBasedFactory
from samcli.lib.utils.resources import (
    AWS_APIGATEWAY_RESTAPI,
    AWS_APIGATEWAY_V2_API,
    AWS_LAMBDA_FUNCTION,
    AWS_LAMBDA_LAYERVERSION,
    AWS_SERVERLESS_API,
    AWS_SERVERLESS_FUNCTION,
    AWS_SERVERLESS_HTTPAPI,
    AWS_SERVERLESS_LAYERVERSION,
    AWS_SERVERLESS_STATEMACHINE,
    AWS_STEPFUNCTIONS_STATEMACHINE,
)

if TYPE_CHECKING:  # pragma: no cover
    from samcli.commands.deploy.deploy_context import DeployContext
    from samcli.commands.sync.sync_context import SyncContext

LOG = logging.getLogger(__name__)


class SyncCodeResources:
    """
    A class that records the supported resource types that can perform sync --code
    """

    _accepted_resources = [
        AWS_SERVERLESS_FUNCTION,
        AWS_LAMBDA_FUNCTION,
        AWS_SERVERLESS_LAYERVERSION,
        AWS_LAMBDA_LAYERVERSION,
        AWS_SERVERLESS_API,
        AWS_APIGATEWAY_RESTAPI,
        AWS_SERVERLESS_HTTPAPI,
        AWS_APIGATEWAY_V2_API,
        AWS_SERVERLESS_STATEMACHINE,
        AWS_STEPFUNCTIONS_STATEMACHINE,
    ]

    @classmethod
    def values(cls) -> List[str]:
        """
        A class getter to retrieve the accepted resource list

        Returns: List[str]
            The accepted resources list
        """
        return cls._accepted_resources


class SyncFlowFactory(ResourceTypeBasedFactory[SyncFlow]):  # pylint: disable=E1136
    """Factory class for SyncFlow
    Creates appropriate SyncFlow types based on stack resource types
    """

    _deploy_context: "DeployContext"
    _build_context: "BuildContext"
    _sync_context: "SyncContext"
    _physical_id_mapping: Dict[str, str]
    _auto_dependency_layer: bool

    def __init__(
        self,
        build_context: "BuildContext",
        deploy_context: "DeployContext",
        sync_context: "SyncContext",
        stacks: List[Stack],
        auto_dependency_layer: bool,
    ) -> None:
        """
        Parameters
        ----------
        build_context : BuildContext
            BuildContext to be passed into each individual SyncFlow
        deploy_context : DeployContext
            DeployContext to be passed into each individual SyncFlow
        sync_context: SyncContext
            SyncContext object that obtains sync information.
        stacks : List[Stack]
            List of stacks containing a root stack and optional nested ones
        """
        super().__init__(stacks)
        self._deploy_context = deploy_context
        self._build_context = build_context
        self._sync_context = sync_context
        self._auto_dependency_layer = auto_dependency_layer
        self._physical_id_mapping = dict()

    def load_physical_id_mapping(self) -> None:
        """Load physical IDs of the stack resources from remote"""
        LOG.debug("Loading physical ID mapping")
        resource_provider = get_boto_resource_provider_with_config(
            region=self._deploy_context.region, profile=self._deploy_context.profile
        )
        client_provider = get_boto_client_provider_with_config(
            region=self._deploy_context.region, profile=self._deploy_context.profile
        )

        try:
            resource_mapping = get_resource_summaries(
                boto_resource_provider=resource_provider,
                boto_client_provider=client_provider,
                stack_name=self._deploy_context.stack_name,
            )
        except ClientError as ex:
            error_code = get_client_error_code(ex)
            if error_code == "ValidationError":
                raise InvalidStackNameException(
                    f"Invalid --stack-name parameter. Stack with id '{self._deploy_context.stack_name}' does not exist"
                ) from ex
            raise ex

        # get the resource_id -> physical_id mapping
        self._physical_id_mapping = {
            resource_id: summary.physical_resource_id for resource_id, summary in resource_mapping.items()
        }

    def _create_lambda_flow(
        self,
        resource_identifier: ResourceIdentifier,
        application_build_result: Optional[ApplicationBuildResult],
    ) -> Optional[FunctionSyncFlow]:
        function = self._build_context.function_provider.get(str(resource_identifier))
        if not function:
            LOG.warning("Can't find function resource with '%s' logical id", str(resource_identifier))
            return None

        if function.packagetype == ZIP:
            return self._create_zip_type_lambda_flow(resource_identifier, application_build_result, function)
        if function.packagetype == IMAGE:
            return self._create_image_type_lambda_flow(resource_identifier, application_build_result, function)
        return None

    def _create_zip_type_lambda_flow(
        self,
        resource_identifier: ResourceIdentifier,
        application_build_result: Optional[ApplicationBuildResult],
        function: Function,
    ) -> Optional[FunctionSyncFlow]:
        if not function.function_build_info.is_buildable():
            if function.function_build_info == FunctionBuildInfo.InlineCode:
                LOG.debug(
                    "No need to create sync flow for a function with InlineCode '%s' resource", str(resource_identifier)
                )
                return None
            if function.function_build_info == FunctionBuildInfo.PreZipped:
                # if codeuri points to zip file, use ZipFunctionSyncFlowSkipBuildZipFile sync flow
                LOG.debug("Creating ZipFunctionSyncFlowSkipBuildZipFile for '%s' resource", resource_identifier)
                return ZipFunctionSyncFlowSkipBuildZipFile(
                    str(resource_identifier),
                    self._build_context,
                    self._deploy_context,
                    self._sync_context,
                    self._physical_id_mapping,
                    self._stacks,
                    application_build_result,
                )

            if function.function_build_info == FunctionBuildInfo.SkipBuild:
                # if function is marked with SkipBuild, use ZipFunctionSyncFlowSkipBuildDirectory sync flow
                LOG.debug("Creating ZipFunctionSyncFlowSkipBuildDirectory for '%s' resource", resource_identifier)
                return ZipFunctionSyncFlowSkipBuildDirectory(
                    str(resource_identifier),
                    self._build_context,
                    self._deploy_context,
                    self._sync_context,
                    self._physical_id_mapping,
                    self._stacks,
                    application_build_result,
                )

        # only return auto dependency layer sync if runtime is supported
        if self._auto_dependency_layer and NestedStackManager.is_runtime_supported(function.runtime):
            return AutoDependencyLayerParentSyncFlow(
                str(resource_identifier),
                self._build_context,
                self._deploy_context,
                self._sync_context,
                self._physical_id_mapping,
                self._stacks,
                application_build_result,
            )

        return ZipFunctionSyncFlow(
            str(resource_identifier),
            self._build_context,
            self._deploy_context,
            self._sync_context,
            self._physical_id_mapping,
            self._stacks,
            application_build_result,
        )

    def _create_image_type_lambda_flow(
        self,
        resource_identifier: ResourceIdentifier,
        application_build_result: Optional[ApplicationBuildResult],
        function: Function,
    ) -> Optional[FunctionSyncFlow]:
        if not function.function_build_info.is_buildable():
            LOG.warning("Can't build image type function with '%s' logical id", str(resource_identifier))
            return None

        return ImageFunctionSyncFlow(
            str(resource_identifier),
            self._build_context,
            self._deploy_context,
            self._sync_context,
            self._physical_id_mapping,
            self._stacks,
            application_build_result,
        )

    def _create_layer_flow(
        self,
        resource_identifier: ResourceIdentifier,
        application_build_result: Optional[ApplicationBuildResult],
    ) -> Optional[SyncFlow]:
        layer = self._build_context.layer_provider.get(str(resource_identifier))
        if not layer:
            LOG.warning("Can't find layer resource with '%s' logical id", str(resource_identifier))
            return None

        if BuildContext.is_layer_buildable(layer):
            return LayerSyncFlow(
                str(resource_identifier),
                self._build_context,
                self._deploy_context,
                self._sync_context,
                self._physical_id_mapping,
                self._stacks,
                application_build_result,
            )

        if is_local_folder(layer.codeuri):
            LOG.debug("Creating LayerSyncFlowSkipBuildDirectory for '%s' resource", resource_identifier)
            return LayerSyncFlowSkipBuildDirectory(
                str(resource_identifier),
                self._build_context,
                self._deploy_context,
                self._sync_context,
                self._physical_id_mapping,
                self._stacks,
                application_build_result,
            )

        if is_zip_file(layer.codeuri):
            LOG.debug("Creating LayerSyncFlowSkipBuildZipFile for '%s' resource", resource_identifier)
            return LayerSyncFlowSkipBuildZipFile(
                str(resource_identifier),
                self._build_context,
                self._deploy_context,
                self._sync_context,
                self._physical_id_mapping,
                self._stacks,
                application_build_result,
            )

        LOG.warning("Can't create sync flow for '%s' layer resource", resource_identifier)
        return None

    def _create_rest_api_flow(
        self,
        resource_identifier: ResourceIdentifier,
        application_build_result: Optional[ApplicationBuildResult],
    ) -> SyncFlow:
        return RestApiSyncFlow(
            str(resource_identifier),
            self._build_context,
            self._deploy_context,
            self._sync_context,
            self._physical_id_mapping,
            self._stacks,
        )

    def _create_api_flow(
        self,
        resource_identifier: ResourceIdentifier,
        application_build_result: Optional[ApplicationBuildResult],
    ) -> SyncFlow:
        return HttpApiSyncFlow(
            str(resource_identifier),
            self._build_context,
            self._deploy_context,
            self._sync_context,
            self._physical_id_mapping,
            self._stacks,
        )

    def _create_stepfunctions_flow(
        self,
        resource_identifier: ResourceIdentifier,
        application_build_result: Optional[ApplicationBuildResult],
    ) -> Optional[SyncFlow]:
        return StepFunctionsSyncFlow(
            str(resource_identifier),
            self._build_context,
            self._deploy_context,
            self._sync_context,
            self._physical_id_mapping,
            self._stacks,
        )

    GeneratorFunction = Callable[
        ["SyncFlowFactory", ResourceIdentifier, Optional[ApplicationBuildResult]], Optional[SyncFlow]
    ]
    GENERATOR_MAPPING: Dict[str, GeneratorFunction] = {
        AWS_LAMBDA_FUNCTION: _create_lambda_flow,
        AWS_SERVERLESS_FUNCTION: _create_lambda_flow,
        AWS_SERVERLESS_LAYERVERSION: _create_layer_flow,
        AWS_LAMBDA_LAYERVERSION: _create_layer_flow,
        AWS_SERVERLESS_API: _create_rest_api_flow,
        AWS_APIGATEWAY_RESTAPI: _create_rest_api_flow,
        AWS_SERVERLESS_HTTPAPI: _create_api_flow,
        AWS_APIGATEWAY_V2_API: _create_api_flow,
        AWS_SERVERLESS_STATEMACHINE: _create_stepfunctions_flow,
        AWS_STEPFUNCTIONS_STATEMACHINE: _create_stepfunctions_flow,
    }

    # SyncFlow mapping between resource type and creation function
    # Ignoring no-self-use as PyLint has a bug with Generic Abstract Classes
    def _get_generator_mapping(self) -> Dict[str, GeneratorFunction]:  # pylint: disable=no-self-use
        return SyncFlowFactory.GENERATOR_MAPPING

    def create_sync_flow(
        self, resource_identifier: ResourceIdentifier, application_build_result: Optional[ApplicationBuildResult] = None
    ) -> Optional[SyncFlow]:
        generator = self._get_generator_function(resource_identifier)
        if not generator:
            return None
        return cast(SyncFlowFactory.GeneratorFunction, generator)(self, resource_identifier, application_build_result)
