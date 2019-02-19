"""
Class that provides functions from a given SAM template
"""

import logging
import six

from .exceptions import InvalidLayerReference
from .provider import FunctionProvider, Function, LayerVersion
from .sam_base_provider import SamBaseProvider
from .sam_function_code_provider import SamFunctionCodeProvider

LOG = logging.getLogger(__name__)


class SamFunctionProvider(FunctionProvider):
    """
    Fetches and returns Lambda Functions from a SAM Template. The SAM template passed to this provider is assumed
    to be valid, normalized and a dictionary.

    It may or may not contain a function.
    """

    _SERVERLESS_FUNCTION = "AWS::Serverless::Function"
    _LAMBDA_FUNCTION = "AWS::Lambda::Function"
    _SERVERLESS_LAYER = "AWS::Serverless::LayerVersion"
    _LAMBDA_LAYER = "AWS::Lambda::LayerVersion"
    _DEFAULT_CODEURI = "."

    def __init__(self, template_dict, parameter_overrides=None):
        """
        Initialize the class with SAM template data. The SAM template passed to this provider is assumed
        to be valid, normalized and a dictionary. It should be normalized by running all pre-processing
        before passing to this class. The process of normalization will remove structures like ``Globals``, resolve
        intrinsic functions etc.
        This class does not perform any syntactic validation of the template.

        After the class is initialized, any changes to the ``template_dict`` will not be reflected in here.
        You need to explicitly update the class with new template, if necessary.

        :param dict template_dict: SAM Template as a dictionary
        :param dict parameter_overrides: Optional dictionary of values for SAM template parameters that might want
            to get substituted within the template
        """

        self.template_dict = SamBaseProvider.get_template(template_dict, parameter_overrides)
        self.resources = self.template_dict.get("Resources", {})

        LOG.debug("%d resources found in the template", len(self.resources))

        # Store a map of function name to function information for quick reference
        self.functions = self._extract_functions(self.resources)

    def get(self, name):
        """
        Returns the function given name or LogicalId of the function. Every SAM resource has a logicalId, but it may
        also have a function name. This method searches only for LogicalID and returns the function that matches
        it.

        :param string name: Name of the function
        :return Function: namedtuple containing the Function information if function is found.
                          None, if function is not found
        :raises ValueError If name is not given
        """

        if not name:
            raise ValueError("Function name is required")

        return self.functions.get(name)

    def get_all(self):
        """
        Yields all the Lambda functions available in the SAM Template.

        :yields Function: namedtuple containing the function information
        """

        for _, function in self.functions.items():
            yield function

    @staticmethod
    def _parse_function_code(name, resource_properties, resource_type):
        """
        Simple method to wrap SamFunctionCodeProvider instantiation, easier to test

        :param str name: Logical Id of the function
        :param dict resource_properties: Function Properties Dictionary
        :param str resource_type: Function type AWS::Serverless::Function || AWS::Lambda::Function
        """
        return SamFunctionCodeProvider(name, resource_properties, resource_type)

    @staticmethod
    def _extract_functions(resources):
        """
        Extracts and returns function information from the given dictionary of SAM/CloudFormation resources. This
        method supports functions defined with AWS::Serverless::Function and AWS::Lambda::Function

        :param dict resources: Dictionary of SAM/CloudFormation resources
        :return dict(string : samcli.commands.local.lib.provider.Function): Dictionary of function LogicalId to the
            Function configuration object
        """

        result = {}

        for name, resource in resources.items():

            resource_type = resource.get("Type")
            resource_properties = resource.get("Properties", {})

            if resource_type == SamFunctionProvider._SERVERLESS_FUNCTION:
                layers = SamFunctionProvider._parse_layer_info(resource_properties.get("Layers", []), resources)
                codeuri = SamFunctionProvider._parse_function_code(name, resource_properties, resource_type)
                result[name] = SamFunctionProvider._convert_sam_function_resource(
                    name, resource_properties, layers, codeuri
                )

            elif resource_type == SamFunctionProvider._LAMBDA_FUNCTION:
                layers = SamFunctionProvider._parse_layer_info(resource_properties.get("Layers", []), resources)
                codeuri = SamFunctionProvider._parse_function_code(name, resource_properties, resource_type)
                result[name] = SamFunctionProvider._convert_lambda_function_resource(
                    name, resource_properties, layers, codeuri
                )

            # We don't care about other resource types. Just ignore them

        return result

    @staticmethod
    def _convert_sam_function_resource(name, resource_properties, layers, codeuri):
        """
        Converts a AWS::Serverless::Function resource to a Function configuration usable by the provider.

        :param string name: LogicalID of the resource NOTE: This is *not* the function name because not all functions
            declare a name
        :param dict resource_properties: Properties of this resource
        :return samcli.commands.local.lib.provider.Function: Function configuration
        """

        LOG.debug("Found Serverless function with name='%s' and CodeUri='%s'", name, codeuri)

        return Function(
            name=name,
            runtime=resource_properties.get("Runtime"),
            memory=resource_properties.get("MemorySize"),
            timeout=resource_properties.get("Timeout"),
            handler=resource_properties.get("Handler"),
            codeuri=codeuri,
            environment=resource_properties.get("Environment"),
            rolearn=resource_properties.get("Role"),
            layers=layers
        )

    @staticmethod
    def _convert_lambda_function_resource(name, resource_properties, layers, codeuri):  # pylint: disable=invalid-name
        """
        Converts a AWS::Serverless::Function resource to a Function configuration usable by the provider.

        :param string name: LogicalID of the resource NOTE: This is *not* the function name because not all functions
            declare a name
        :param dict resource_properties: Properties of this resource
        :return samcli.commands.local.lib.provider.Function: Function configuration
        """

        LOG.debug("Found Lambda function with name='%s' and CodeUri='%s'", name, codeuri)

        return Function(
            name=name,
            runtime=resource_properties.get("Runtime"),
            memory=resource_properties.get("MemorySize"),
            timeout=resource_properties.get("Timeout"),
            handler=resource_properties.get("Handler"),
            codeuri=codeuri,
            environment=resource_properties.get("Environment"),
            rolearn=resource_properties.get("Role"),
            layers=layers
        )

    @staticmethod
    def _parse_layer_info(list_of_layers, resources):
        """
        Creates a list of Layer objects that are represented by the resources and the list of layers

        Parameters
        ----------
        list_of_layers List(str)
            List of layers that are defined within the Layers Property on a function
        resources dict
            The Resources dictionary defined in a template

        Returns
        -------
        List(samcli.commands.local.lib.provider.Layer)
            List of the Layer objects created from the template and layer list defined on the function. The order
            of the layers does not change.

            I.E: list_of_layers = ["layer1", "layer2"] the return would be [Layer("layer1"), Layer("layer2")]
        """
        layers = []
        for layer in list_of_layers:
            # If the layer is a string, assume it is the arn
            if isinstance(layer, six.string_types):
                layers.append(LayerVersion(layer, None))
                continue

            # In the list of layers that is defined within a template, you can reference a LayerVersion resource.
            # When running locally, we need to follow that Ref so we can extract the local path to the layer code.
            if isinstance(layer, dict) and layer.get("Ref"):
                layer_logical_id = layer.get("Ref")
                layer_resource = resources.get(layer_logical_id)
                if not layer_resource or \
                        layer_resource.get("Type", "") not in (SamFunctionProvider._SERVERLESS_LAYER,
                                                               SamFunctionProvider._LAMBDA_LAYER):
                    raise InvalidLayerReference()

                layer_properties = layer_resource.get("Properties", {})
                resource_type = layer_resource.get("Type")
                codeuri = None

                if resource_type == SamFunctionProvider._LAMBDA_LAYER:
                    codeuri = SamFunctionCodeProvider.extract_code(
                            layer_properties,
                            "Content"
                    )

                if resource_type == SamFunctionProvider._SERVERLESS_LAYER:
                    codeuri = SamFunctionCodeProvider.extract_codeuri(
                            layer_logical_id,
                            layer_properties,
                            "ContentUri"
                    )

                layers.append(LayerVersion(layer_logical_id, codeuri))

        return layers
