"""
Class that provides functions from a given SAM template
"""
import logging

from samcli.commands.local.cli_common.user_exceptions import InvalidLayerVersionArn
from samcli.lib.providers.exceptions import InvalidLayerReference
from .provider import FunctionProvider, Function, LayerVersion
from .sam_base_provider import SamBaseProvider

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

        for f in self.get_all():
            if f.name == name:
                return f

            if f.functionname == name:
                return f

        return None

    def get_all(self):
        """
        Yields all the Lambda functions available in the SAM Template.

        :yields Function: namedtuple containing the function information
        """

        for _, function in self.functions.items():
            yield function

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
                result[name] = SamFunctionProvider._convert_sam_function_resource(name, resource_properties, layers)

            elif resource_type == SamFunctionProvider._LAMBDA_FUNCTION:
                layers = SamFunctionProvider._parse_layer_info(resource_properties.get("Layers", []), resources)
                result[name] = SamFunctionProvider._convert_lambda_function_resource(name, resource_properties, layers)

            # We don't care about other resource types. Just ignore them

        return result

    @staticmethod
    def _convert_sam_function_resource(name, resource_properties, layers):
        """
        Converts a AWS::Serverless::Function resource to a Function configuration usable by the provider.

        Parameters
        ----------
        name str
            LogicalID of the resource NOTE: This is *not* the function name because not all functions declare a name
        resource_properties dict
            Properties of this resource
        layers List(samcli.commands.local.lib.provider.Layer)
            List of the Layer objects created from the template and layer list defined on the function.

        Returns
        -------
        samcli.commands.local.lib.provider.Function
            Function configuration
        """

        codeuri = SamFunctionProvider._extract_sam_function_codeuri(name, resource_properties, "CodeUri")

        LOG.debug("Found Serverless function with name='%s' and CodeUri='%s'", name, codeuri)

        return SamFunctionProvider._build_function_configuration(name, codeuri, resource_properties, layers)

    @staticmethod
    def _extract_sam_function_codeuri(name, resource_properties, code_property_key):
        """
        Extracts the SAM Function CodeUri from the Resource Properties

        Parameters
        ----------
        name str
            LogicalId of the resource
        resource_properties dict
            Dictionary representing the Properties of the Resource
        code_property_key str
            Property Key of the code on the Resource

        Returns
        -------
        str
            Representing the local code path
        """
        codeuri = resource_properties.get(code_property_key, SamFunctionProvider._DEFAULT_CODEURI)
        # CodeUri can be a dictionary of S3 Bucket/Key or a S3 URI, neither of which are supported
        if isinstance(codeuri, dict) or (isinstance(codeuri, str) and codeuri.startswith("s3://")):
            codeuri = SamFunctionProvider._DEFAULT_CODEURI
            LOG.warning(
                "Lambda function '%s' has specified S3 location for CodeUri which is unsupported. "
                "Using default value of '%s' instead",
                name,
                codeuri,
            )
        return codeuri

    @staticmethod
    def _convert_lambda_function_resource(name, resource_properties, layers):  # pylint: disable=invalid-name
        """
        Converts a AWS::Serverless::Function resource to a Function configuration usable by the provider.

        Parameters
        ----------
        name str
            LogicalID of the resource NOTE: This is *not* the function name because not all functions declare a name
        resource_properties dict
            Properties of this resource
        layers List(samcli.commands.local.lib.provider.Layer)
            List of the Layer objects created from the template and layer list defined on the function.

        Returns
        -------
        samcli.commands.local.lib.provider.Function
            Function configuration
        """

        # CodeUri is set to "." in order to get code locally from current directory. AWS::Lambda::Function's ``Code``
        # property does not support specifying a local path
        codeuri = SamFunctionProvider._extract_lambda_function_code(resource_properties, "Code")

        LOG.debug("Found Lambda function with name='%s' and CodeUri='%s'", name, codeuri)

        return SamFunctionProvider._build_function_configuration(name, codeuri, resource_properties, layers)

    @staticmethod
    def _extract_lambda_function_code(resource_properties, code_property_key):
        """
        Extracts the Lambda Function Code from the Resource Properties

        Parameters
        ----------
        resource_properties dict
            Dictionary representing the Properties of the Resource
        code_property_key str
            Property Key of the code on the Resource

        Returns
        -------
        str
            Representing the local code path
        """

        codeuri = resource_properties.get(code_property_key, SamFunctionProvider._DEFAULT_CODEURI)

        if isinstance(codeuri, dict):
            codeuri = SamFunctionProvider._DEFAULT_CODEURI

        return codeuri

    @staticmethod
    def _build_function_configuration(name, codeuri, resource_properties, layers):
        """
        Builds a Function configuration usable by the provider.

        Parameters
        ----------
        name str
            LogicalID of the resource NOTE: This is *not* the function name because not all functions declare a name
        codeuri str
            Representing the local code path
        resource_properties dict
            Properties of this resource
        layers List(samcli.commands.local.lib.provider.Layer)
            List of the Layer objects created from the template and layer list defined on the function.

        Returns
        -------
        samcli.commands.local.lib.provider.Function
            Function configuration
        """
        return Function(
            name=name,
            functionname=resource_properties.get("FunctionName", name),
            runtime=resource_properties.get("Runtime"),
            memory=resource_properties.get("MemorySize"),
            timeout=resource_properties.get("Timeout"),
            handler=resource_properties.get("Handler"),
            codeuri=codeuri,
            environment=resource_properties.get("Environment"),
            rolearn=resource_properties.get("Role"),
            layers=layers,
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
            if layer == "arn:aws:lambda:::awslayer:AmazonLinux1803":
                LOG.debug("Skipped arn:aws:lambda:::awslayer:AmazonLinux1803 as the containers are AmazonLinux1803")
                continue

            if layer == "arn:aws:lambda:::awslayer:AmazonLinux1703":
                raise InvalidLayerVersionArn(
                    "Building and invoking locally only supports AmazonLinux1803. See "
                    "https://aws.amazon.com/blogs/compute/upcoming-updates-to-the-aws-lambda-execution-environment/ for more detials."
                )  # noqa: E501

            # If the layer is a string, assume it is the arn
            if isinstance(layer, str):
                layers.append(LayerVersion(layer, None))
                continue

            # In the list of layers that is defined within a template, you can reference a LayerVersion resource.
            # When running locally, we need to follow that Ref so we can extract the local path to the layer code.
            if isinstance(layer, dict) and layer.get("Ref"):
                layer_logical_id = layer.get("Ref")
                layer_resource = resources.get(layer_logical_id)
                if not layer_resource or layer_resource.get("Type", "") not in (
                    SamFunctionProvider._SERVERLESS_LAYER,
                    SamFunctionProvider._LAMBDA_LAYER,
                ):
                    raise InvalidLayerReference()

                layer_properties = layer_resource.get("Properties", {})
                resource_type = layer_resource.get("Type")
                codeuri = None

                if resource_type == SamFunctionProvider._LAMBDA_LAYER:
                    codeuri = SamFunctionProvider._extract_lambda_function_code(layer_properties, "Content")

                if resource_type == SamFunctionProvider._SERVERLESS_LAYER:
                    codeuri = SamFunctionProvider._extract_sam_function_codeuri(
                        layer_logical_id, layer_properties, "ContentUri"
                    )

                layers.append(LayerVersion(layer_logical_id, codeuri))

        return layers
