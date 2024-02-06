"""
Factory for creating CodeResourceTriggers
"""

import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, cast

from samcli.lib.providers.provider import ResourceIdentifier, Stack, get_resource_by_id
from samcli.lib.utils.packagetype import IMAGE, ZIP
from samcli.lib.utils.resource_trigger import (
    CodeResourceTrigger,
    DefinitionCodeTrigger,
    LambdaImageCodeTrigger,
    LambdaLayerCodeTrigger,
    LambdaZipCodeTrigger,
)
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

LOG = logging.getLogger(__name__)


class CodeTriggerFactory(ResourceTypeBasedFactory[CodeResourceTrigger]):  # pylint: disable=E1136
    _stacks: List[Stack]

    def __init__(self, stacks: List[Stack], base_dir: Path) -> None:
        self.base_dir = base_dir
        super().__init__(stacks)

    def _create_lambda_trigger(
        self,
        resource_identifier: ResourceIdentifier,
        resource_type: str,
        resource: Dict[str, Any],
        on_code_change: Callable,
        watch_exclude: List[str],
    ):
        package_type = resource.get("Properties", dict()).get("PackageType", ZIP)
        if package_type == ZIP:
            return LambdaZipCodeTrigger(resource_identifier, self._stacks, self.base_dir, on_code_change, watch_exclude)
        if package_type == IMAGE:
            return LambdaImageCodeTrigger(resource_identifier, self._stacks, self.base_dir, on_code_change)
        return None

    def _create_layer_trigger(
        self,
        resource_identifier: ResourceIdentifier,
        resource_type: str,
        resource: Dict[str, Any],
        on_code_change: Callable,
        watch_exclude: List[str],
    ):
        return LambdaLayerCodeTrigger(resource_identifier, self._stacks, self.base_dir, on_code_change, watch_exclude)

    def _create_definition_code_trigger(
        self,
        resource_identifier: ResourceIdentifier,
        resource_type: str,
        resource: Dict[str, Any],
        on_code_change: Callable,
        watch_exclude: List[str],
    ):
        return DefinitionCodeTrigger(resource_identifier, resource_type, self._stacks, self.base_dir, on_code_change)

    GeneratorFunction = Callable[
        ["CodeTriggerFactory", ResourceIdentifier, str, Dict[str, Any], Callable, List[str]],
        Optional[CodeResourceTrigger],
    ]
    GENERATOR_MAPPING: Dict[str, GeneratorFunction] = {
        AWS_LAMBDA_FUNCTION: _create_lambda_trigger,
        AWS_SERVERLESS_FUNCTION: _create_lambda_trigger,
        AWS_SERVERLESS_LAYERVERSION: _create_layer_trigger,
        AWS_LAMBDA_LAYERVERSION: _create_layer_trigger,
        AWS_SERVERLESS_API: _create_definition_code_trigger,
        AWS_APIGATEWAY_RESTAPI: _create_definition_code_trigger,
        AWS_SERVERLESS_HTTPAPI: _create_definition_code_trigger,
        AWS_APIGATEWAY_V2_API: _create_definition_code_trigger,
        AWS_SERVERLESS_STATEMACHINE: _create_definition_code_trigger,
        AWS_STEPFUNCTIONS_STATEMACHINE: _create_definition_code_trigger,
    }

    # Ignoring no-self-use as PyLint has a bug with Generic Abstract Classes
    def _get_generator_mapping(self) -> Dict[str, GeneratorFunction]:  # pylint: disable=no-self-use
        return CodeTriggerFactory.GENERATOR_MAPPING

    def create_trigger(
        self, resource_identifier: ResourceIdentifier, on_code_change: Callable, watch_exclude: List[str]
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
        resource_type = self._get_resource_type(resource_identifier)
        if not generator or not resource or not resource_type:
            return None
        return cast(CodeTriggerFactory.GeneratorFunction, generator)(
            self, resource_identifier, resource_type, resource, on_code_change, watch_exclude
        )
