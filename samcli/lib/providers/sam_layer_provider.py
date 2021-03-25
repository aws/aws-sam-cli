"""
Class that provides layers from a given SAM template
"""
import logging
import posixpath
from typing import List, Dict, Optional

from .provider import LayerVersion, Stack
from .sam_base_provider import SamBaseProvider
from .sam_stack_provider import SamLocalStackProvider

LOG = logging.getLogger(__name__)


class SamLayerProvider(SamBaseProvider):
    """
    Fetches and returns Layers from a SAM Template. The SAM template passed to this provider is assumed to be valid,
    normalized and a dictionary.

    It may or may not contain a layer.
    """

    def __init__(self, stacks: List[Stack], use_raw_codeuri: bool = False) -> None:
        """
        Initialize the class with SAM template data. The SAM template passed to this provider is assumed
        to be valid, normalized and a dictionary. It should be normalized by running all pre-processing
        before passing to this class. The process of normalization will remove structures like ``Globals``, resolve
        intrinsic functions etc.
        This class does not perform any syntactic validation of the template.

        After the class is initialized, any changes to the ``template_dict`` will not be reflected in here.
        You need to explicitly update the class with new template, if necessary.

        Parameters
        ----------
        :param dict stacks: List of stacks layers are extracted from
        :param bool use_raw_codeuri: Do not resolve adjust core_uri based on the template path, use the raw uri.
            Note(xinhol): use_raw_codeuri is temporary to fix a bug, and will be removed for a permanent solution.
        """
        self._stacks = stacks
        self._use_raw_codeuri = use_raw_codeuri

        self._layers = self._extract_layers()

    def get(self, name: str) -> Optional[LayerVersion]:
        """
        Returns the layer with given name or logical id.
        If it is in a nested stack, name can be prefixed with stack path to avoid ambiguity

        Parameters
        ----------
        name: name or logical id of the layer.

        Returns
        -------
        LayerVersion object of one layer.

        """
        if not name:
            raise ValueError("Layer name is required")

        for layer in self._layers:
            if posixpath.join(layer.stack_path, layer.name) == name or layer.name == name:
                return layer
        return None

    def get_all(self) -> List[LayerVersion]:
        """
        Returns all Layers in template
        Returns
        -------
        [LayerVersion] list of layer version objects.
        """
        return self._layers

    def _extract_layers(self) -> List[LayerVersion]:
        """
        Extracts all resources with Type AWS::Lambda::LayerVersion and AWS::Serverless::LayerVersion and return a list
        of those resources.
        """
        layers = []
        for stack in self._stacks:
            for name, resource in stack.resources.items():
                if resource.get("Type") in [self.LAMBDA_LAYER, self.SERVERLESS_LAYER]:
                    layers.append(self._convert_lambda_layer_resource(stack, name, resource))
        return layers

    def _convert_lambda_layer_resource(self, stack: Stack, layer_logical_id: str, layer_resource: Dict) -> LayerVersion:
        """
        Convert layer resource into {LayerVersion} object.
        Parameters
        ----------
        layer_logical_id: LogicalID of resource.
        layer_resource: resource in template.
        """
        # In the list of layers that is defined within a template, you can reference a LayerVersion resource.
        # When running locally, we need to follow that Ref so we can extract the local path to the layer code.
        layer_properties = layer_resource.get("Properties", {})
        resource_type = layer_resource.get("Type")
        compatible_runtimes = layer_properties.get("CompatibleRuntimes")
        codeuri = None

        if resource_type == self.SERVERLESS_LAYER:
            codeuri = SamLayerProvider._extract_sam_function_codeuri(layer_logical_id, layer_properties, "ContentUri")
        if resource_type == self.LAMBDA_LAYER:
            codeuri = SamLayerProvider._extract_lambda_function_code(layer_properties, "Content")

        if codeuri and not self._use_raw_codeuri:
            LOG.debug("--base-dir is presented not, adjusting uri %s relative to %s", codeuri, stack.location)
            codeuri = SamLocalStackProvider.normalize_resource_path(stack.location, codeuri)

        return LayerVersion(
            layer_logical_id,
            codeuri,
            compatible_runtimes,
            layer_resource.get("Metadata", None),
            stack_path=stack.stack_path,
        )
