"""
Class that provides layers from a given SAM template
"""
import logging

from .provider import LayerVersion
from .sam_base_provider import SamBaseProvider

LOG = logging.getLogger(__name__)


class SamLayerProvider(SamBaseProvider):
    """
    Fetches and returns Layers from a SAM Template. The SAM template passed to this provider is assumed to be valid,
    normalized and a dictionary.

    It may or may not contain a layer.
    """

    def __init__(self, template_dict, parameter_overrides=None):
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
        template_dict: SAM Template as a dictionary
        parameter_overrides: Optional dictionary of values for SAM template parameters that might want to get
            substituted within the template
        """
        self._template_dict = SamLayerProvider.get_template(template_dict, parameter_overrides)
        self._resources = self._template_dict.get("Resources", {})
        self._layers = self._extract_layers()

    def get(self, name):
        """
        Returns the layer with given name or logical id.

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
            if layer.name == name:
                return layer
        return None

    def get_all(self):
        """
        Returns all Layers in template
        Returns
        -------
        [LayerVersion] list of layer version objects.
        """
        return self._layers

    def _extract_layers(self):
        """
        Extracts all resources with Type AWS::Lambda::LayerVersion and AWS::Serverless::LayerVersion and return a list
        of those resources.
        """
        layers = []
        for name, resource in self._resources.items():
            if resource.get("Type") in [self.LAMBDA_LAYER, self.SERVERLESS_LAYER]:
                layers.append(self._convert_lambda_layer_resource(name, resource))
        return layers

    def _convert_lambda_layer_resource(self, layer_logical_id, layer_resource):
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

        return LayerVersion(layer_logical_id, codeuri, compatible_runtimes, layer_resource.get("Metadata", None))
