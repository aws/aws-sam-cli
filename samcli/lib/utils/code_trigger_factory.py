"""
Factory for creating CodeResourceTriggers
"""
import logging

from typing import Any, Callable, Dict, List, Optional, cast

from samcli.lib.utils.packagetype import IMAGE, ZIP
from samcli.lib.utils.resource_trigger import (
    APIGatewayCodeTrigger,
    CodeResourceTrigger,
    LambdaImageCodeTrigger,
    LambdaLayerCodeTrigger,
    LambdaZipCodeTrigger,
)
from samcli.lib.utils.resource_type_based_factory import ResourceTypeBasedFactory

from samcli.lib.providers.sam_base_provider import SamBaseProvider
from samcli.lib.providers.sam_api_provider import SamApiProvider
from samcli.lib.providers.cfn_api_provider import CfnApiProvider
from samcli.lib.providers.provider import ResourceIdentifier, Stack, get_resource_by_id

LOG = logging.getLogger(__name__)


class CodeTriggerFactory(ResourceTypeBasedFactory[CodeResourceTrigger]):  # pylint: disable=E1136
    _stacks: List[Stack]

    def _create_lambda_trigger(
        self, resource_identifier: ResourceIdentifier, resource: Dict[str, Any], on_code_change: Callable
    ):
        package_type = resource.get("Properties", dict()).get("PackageType", ZIP)
        if package_type == ZIP:
            return LambdaZipCodeTrigger(resource_identifier, self._stacks, on_code_change)
        if package_type == IMAGE:
            return LambdaImageCodeTrigger(resource_identifier, self._stacks, on_code_change)
        return None

    def _create_layer_trigger(
        self, resource_identifier: ResourceIdentifier, resource: Dict[str, Any], on_code_change: Callable
    ):
        return LambdaLayerCodeTrigger(resource_identifier, self._stacks, on_code_change)

    def _create_api_gateway_trigger(
        self, resource_identifier: ResourceIdentifier, resource: Dict[str, Any], on_code_change: Callable
    ):
        return APIGatewayCodeTrigger(resource_identifier, self._stacks, on_code_change)

    GeneratorFunction = Callable[
        ["CodeTriggerFactory", ResourceIdentifier, Dict[str, Any], Callable], Optional[CodeResourceTrigger]
    ]
    GENERATOR_MAPPING: Dict[str, GeneratorFunction] = {
        SamBaseProvider.LAMBDA_FUNCTION: _create_lambda_trigger,
        SamBaseProvider.SERVERLESS_FUNCTION: _create_lambda_trigger,
        SamBaseProvider.SERVERLESS_LAYER: _create_layer_trigger,
        SamBaseProvider.LAMBDA_LAYER: _create_layer_trigger,
        SamApiProvider.SERVERLESS_API: _create_api_gateway_trigger,
        CfnApiProvider.APIGATEWAY_RESTAPI: _create_api_gateway_trigger,
        SamApiProvider.SERVERLESS_HTTP_API: _create_api_gateway_trigger,
        CfnApiProvider.APIGATEWAY_V2_API: _create_api_gateway_trigger,
    }

    # Ignoring no-self-use as PyLint has a bug with Generic Abstract Classes
    def _get_generator_mapping(self) -> Dict[str, GeneratorFunction]:  # pylint: disable=no-self-use
        return CodeTriggerFactory.GENERATOR_MAPPING

    def create_trigger(
        self, resource_identifier: ResourceIdentifier, on_code_change: Callable
    ) -> Optional[CodeResourceTrigger]:
        """Create Trigger for the resource type

        Parameters
        ----------
        resource_identifier : ResourceIdentifier
            Resource associated with the trigger
        on_code_change : Callable
            Callback for code change

        Returns
        -------
        Optional[CodeResourceTrigger]
            CodeResourceTrigger for the resource
        """
        resource = get_resource_by_id(self._stacks, resource_identifier)
        generator = self._get_generator_function(resource_identifier)
        if not generator or not resource:
            return None
        return cast(CodeTriggerFactory.GeneratorFunction, generator)(
            self, resource_identifier, resource, on_code_change
        )
