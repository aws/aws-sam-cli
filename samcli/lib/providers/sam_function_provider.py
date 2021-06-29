"""
Class that provides functions from a given SAM template
"""
import logging
from typing import Dict, List, Optional, cast, Iterator, Any

from samcli.commands.local.cli_common.user_exceptions import InvalidLayerVersionArn
from samcli.lib.providers.exceptions import InvalidLayerReference
from samcli.lib.utils.colors import Colored
from samcli.lib.utils.packagetype import ZIP, IMAGE
from .provider import Function, LayerVersion, Stack
from .sam_base_provider import SamBaseProvider
from .sam_stack_provider import SamLocalStackProvider

LOG = logging.getLogger(__name__)


class SamFunctionProvider(SamBaseProvider):
    """
    Fetches and returns Lambda Functions from a SAM Template. The SAM template passed to this provider is assumed
    to be valid, normalized and a dictionary.

    It may or may not contain a function.
    """

    def __init__(
        self, stacks: List[Stack], use_raw_codeuri: bool = False, ignore_code_extraction_warnings: bool = False
    ) -> None:
        """
        Initialize the class with SAM template data. The SAM template passed to this provider is assumed
        to be valid, normalized and a dictionary. It should be normalized by running all pre-processing
        before passing to this class. The process of normalization will remove structures like ``Globals``, resolve
        intrinsic functions etc.
        This class does not perform any syntactic validation of the template.

        After the class is initialized, any changes to the ``template_dict`` will not be reflected in here.
        You need to explicitly update the class with new template, if necessary.

        :param dict stacks: List of stacks functions are extracted from
        :param bool use_raw_codeuri: Do not resolve adjust core_uri based on the template path, use the raw uri.
            Note(xinhol): use_raw_codeuri is temporary to fix a bug, and will be removed for a permanent solution.
        :param bool ignore_code_extraction_warnings: Ignores Log warnings
        """

        self.stacks = stacks

        for stack in stacks:
            LOG.debug("%d resources found in the stack %s", len(stack.resources), stack.stack_path)

        # Store a map of function full_path to function information for quick reference
        self.functions = SamFunctionProvider._extract_functions(
            self.stacks, use_raw_codeuri, ignore_code_extraction_warnings
        )

        self._deprecated_runtimes = {"nodejs4.3", "nodejs6.10", "nodejs8.10", "dotnetcore2.0"}
        self._colored = Colored()

    def get(self, name: str) -> Optional[Function]:
        """
        Returns the function given name or LogicalId of the function. Every SAM resource has a logicalId, but it may
        also have a function name. This method searches only for LogicalID and returns the function that matches.
        If it is in a nested stack, "name" can be prefixed with stack path to avoid ambiguity.
        For example, if a function with name "FunctionA" is located in StackN, which is a nested stack in root stack,
          either "StackN/FunctionA" or "FunctionA" can be used.

        :param string name: Name of the function
        :return Function: namedtuple containing the Function information if function is found.
                          None, if function is not found
        :raises ValueError If name is not given
        """

        if not name:
            raise ValueError("Function name is required")

        # support lookup by full_path
        if name in self.functions:
            return self.functions.get(name)

        for f in self.get_all():
            if name in (f.name, f.functionname):
                self._deprecate_notification(f.runtime)
                return f

        return None

    def _deprecate_notification(self, runtime: Optional[str]) -> None:
        if runtime in self._deprecated_runtimes:
            message = (
                f"WARNING: {runtime} is no longer supported by AWS Lambda, "
                "please update to a newer supported runtime. SAM CLI "
                f"will drop support for all deprecated runtimes {self._deprecated_runtimes} on May 1st. "
                "See issue: https://github.com/awslabs/aws-sam-cli/issues/1934 for more details."
            )
            LOG.warning(self._colored.yellow(message))

    def get_all(self) -> Iterator[Function]:
        """
        Yields all the Lambda functions available in the SAM Template.

        :yields Function: namedtuple containing the function information
        """

        for _, function in self.functions.items():
            yield function

    @staticmethod
    def _extract_functions(
        stacks: List[Stack], use_raw_codeuri: bool = False, ignore_code_extraction_warnings: bool = False
    ) -> Dict[str, Function]:
        """
        Extracts and returns function information from the given dictionary of SAM/CloudFormation resources. This
        method supports functions defined with AWS::Serverless::Function and AWS::Lambda::Function

        :param stacks: List of SAM/CloudFormation stacks to extract functions from
        :param bool use_raw_codeuri: Do not resolve adjust core_uri based on the template path, use the raw uri.
        :param bool ignore_code_extraction_warnings: suppress log statements on code extraction from resources.
        :return dict(string : samcli.commands.local.lib.provider.Function): Dictionary of function full_path to the
            Function configuration object
        """

        result: Dict[str, Function] = {}  # a dict with full_path as key and extracted function as value
        for stack in stacks:
            for name, resource in stack.resources.items():

                resource_type = resource.get("Type")
                resource_properties = resource.get("Properties", {})
                resource_metadata = resource.get("Metadata", None)
                # Add extra metadata information to properties under a separate field.
                if resource_metadata:
                    resource_properties["Metadata"] = resource_metadata

                if resource_type in [SamFunctionProvider.SERVERLESS_FUNCTION, SamFunctionProvider.LAMBDA_FUNCTION]:
                    resource_package_type = resource_properties.get("PackageType", ZIP)

                    code_property_key = SamBaseProvider.CODE_PROPERTY_KEYS[resource_type]
                    image_property_key = SamBaseProvider.IMAGE_PROPERTY_KEYS[resource_type]

                    if resource_package_type == ZIP and SamBaseProvider._is_s3_location(
                        resource_properties.get(code_property_key)
                    ):

                        # CodeUri can be a dictionary of S3 Bucket/Key or a S3 URI, neither of which are supported
                        if not ignore_code_extraction_warnings:
                            SamFunctionProvider._warn_code_extraction(resource_type, name, code_property_key)
                        continue

                    if resource_package_type == IMAGE and SamBaseProvider._is_ecr_uri(
                        resource_properties.get(image_property_key)
                    ):
                        # ImageUri can be an ECR uri, which is not supported
                        if not ignore_code_extraction_warnings:
                            SamFunctionProvider._warn_imageuri_extraction(resource_type, name, image_property_key)
                        continue

                if resource_type == SamFunctionProvider.SERVERLESS_FUNCTION:
                    layers = SamFunctionProvider._parse_layer_info(
                        stack,
                        resource_properties.get("Layers", []),
                        use_raw_codeuri,
                        ignore_code_extraction_warnings=ignore_code_extraction_warnings,
                    )
                    function = SamFunctionProvider._convert_sam_function_resource(
                        stack,
                        name,
                        resource_properties,
                        layers,
                        use_raw_codeuri,
                    )
                    result[function.full_path] = function

                elif resource_type == SamFunctionProvider.LAMBDA_FUNCTION:
                    layers = SamFunctionProvider._parse_layer_info(
                        stack,
                        resource_properties.get("Layers", []),
                        use_raw_codeuri,
                        ignore_code_extraction_warnings=ignore_code_extraction_warnings,
                    )
                    function = SamFunctionProvider._convert_lambda_function_resource(
                        stack, name, resource_properties, layers, use_raw_codeuri
                    )
                    result[function.full_path] = function

                # We don't care about other resource types. Just ignore them

        return result

    @staticmethod
    def _convert_sam_function_resource(
        stack: Stack,
        name: str,
        resource_properties: Dict,
        layers: List[LayerVersion],
        use_raw_codeuri: bool = False,
    ) -> Function:
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
        codeuri: Optional[str] = SamFunctionProvider.DEFAULT_CODEURI
        inlinecode = resource_properties.get("InlineCode")
        imageuri = None
        packagetype = resource_properties.get("PackageType", ZIP)
        if packagetype == ZIP:
            if inlinecode:
                LOG.debug("Found Serverless function with name='%s' and InlineCode", name)
                codeuri = None
            else:
                codeuri = SamBaseProvider._extract_codeuri(resource_properties, "CodeUri")
                LOG.debug("Found Serverless function with name='%s' and CodeUri='%s'", name, codeuri)
        elif packagetype == IMAGE:
            imageuri = SamFunctionProvider._extract_sam_function_imageuri(resource_properties, "ImageUri")
            LOG.debug("Found Serverless function with name='%s' and ImageUri='%s'", name, imageuri)

        return SamFunctionProvider._build_function_configuration(
            stack, name, codeuri, resource_properties, layers, inlinecode, imageuri, use_raw_codeuri
        )

    @staticmethod
    def _convert_lambda_function_resource(
        stack: Stack, name: str, resource_properties: Dict, layers: List[LayerVersion], use_raw_codeuri: bool = False
    ) -> Function:
        """
        Converts a AWS::Lambda::Function resource to a Function configuration usable by the provider.

        Parameters
        ----------
        name str
            LogicalID of the resource NOTE: This is *not* the function name because not all functions declare a name
        resource_properties dict
            Properties of this resource
        layers List(samcli.commands.local.lib.provider.Layer)
            List of the Layer objects created from the template and layer list defined on the function.
        use_raw_codeuri
            Do not resolve adjust core_uri based on the template path, use the raw uri.

        Returns
        -------
        samcli.commands.local.lib.provider.Function
            Function configuration
        """

        # CodeUri is set to "." in order to get code locally from current directory. AWS::Lambda::Function's ``Code``
        # property does not support specifying a local path
        codeuri: Optional[str] = SamFunctionProvider.DEFAULT_CODEURI
        inlinecode = None
        imageuri = None
        packagetype = resource_properties.get("PackageType", ZIP)
        if packagetype == ZIP:
            if (
                "Code" in resource_properties
                and isinstance(resource_properties["Code"], dict)
                and resource_properties["Code"].get("ZipFile")
            ):
                inlinecode = resource_properties["Code"]["ZipFile"]
                LOG.debug("Found Lambda function with name='%s' and Code ZipFile", name)
                codeuri = None
            else:
                codeuri = SamBaseProvider._extract_codeuri(resource_properties, "Code")
                LOG.debug("Found Lambda function with name='%s' and CodeUri='%s'", name, codeuri)
        elif packagetype == IMAGE:
            imageuri = SamFunctionProvider._extract_lambda_function_imageuri(resource_properties, "Code")
            LOG.debug("Found Lambda function with name='%s' and Imageuri='%s'", name, imageuri)

        return SamFunctionProvider._build_function_configuration(
            stack, name, codeuri, resource_properties, layers, inlinecode, imageuri, use_raw_codeuri
        )

    @staticmethod
    def _build_function_configuration(
        stack: Stack,
        name: str,
        codeuri: Optional[str],
        resource_properties: Dict,
        layers: List,
        inlinecode: Optional[str],
        imageuri: Optional[str],
        use_raw_codeuri: bool = False,
    ) -> Function:
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
        use_raw_codeuri
            Do not resolve adjust core_uri based on the template path, use the raw uri.

        Returns
        -------
        samcli.commands.local.lib.provider.Function
            Function configuration
        """
        metadata = resource_properties.get("Metadata", None)
        if metadata and "DockerContext" in metadata and not use_raw_codeuri:
            LOG.debug(
                "--base-dir is not presented, adjusting uri %s relative to %s",
                metadata["DockerContext"],
                stack.location,
            )
            metadata["DockerContext"] = SamLocalStackProvider.normalize_resource_path(
                stack.location, metadata["DockerContext"]
            )

        if codeuri and not use_raw_codeuri:
            LOG.debug("--base-dir is not presented, adjusting uri %s relative to %s", codeuri, stack.location)
            codeuri = SamLocalStackProvider.normalize_resource_path(stack.location, codeuri)

        return Function(
            stack_path=stack.stack_path,
            name=name,
            functionname=resource_properties.get("FunctionName", name),
            packagetype=resource_properties.get("PackageType", ZIP),
            runtime=resource_properties.get("Runtime"),
            memory=resource_properties.get("MemorySize"),
            timeout=resource_properties.get("Timeout"),
            handler=resource_properties.get("Handler"),
            codeuri=codeuri,
            imageuri=imageuri if imageuri else resource_properties.get("ImageUri"),
            imageconfig=resource_properties.get("ImageConfig"),
            environment=resource_properties.get("Environment"),
            rolearn=resource_properties.get("Role"),
            events=resource_properties.get("Events"),
            layers=layers,
            metadata=metadata,
            inlinecode=inlinecode,
            codesign_config_arn=resource_properties.get("CodeSigningConfigArn", None),
        )

    @staticmethod
    def _parse_layer_info(
        stack: Stack,
        list_of_layers: List[Any],
        use_raw_codeuri: bool = False,
        ignore_code_extraction_warnings: bool = False,
    ) -> List[LayerVersion]:
        """
        Creates a list of Layer objects that are represented by the resources and the list of layers

        Parameters
        ----------
        stack : Stack
            The stack the layer is defined in
        list_of_layers : List[Any]
            List of layers that are defined within the Layers Property on a function,
            layer can be defined as string or Dict, in case customers define it in other types, use "Any" here.
        use_raw_codeuri : bool
            Do not resolve adjust core_uri based on the template path, use the raw uri.
        ignore_code_extraction_warnings : bool
            Whether to print warning when codeuri is not a local pth

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
                    "https://aws.amazon.com/blogs/compute/upcoming-updates-to-the-aws-lambda-execution-environment/ "
                    "for more detials."
                )  # noqa: E501

            # If the layer is a string, assume it is the arn
            if isinstance(layer, str):
                layers.append(
                    LayerVersion(
                        layer,
                        None,
                        stack_path=stack.stack_path,
                    )
                )
                continue

            # In the list of layers that is defined within a template, you can reference a LayerVersion resource.
            # When running locally, we need to follow that Ref so we can extract the local path to the layer code.
            if isinstance(layer, dict) and layer.get("Ref"):
                found_layer = SamFunctionProvider._locate_layer_from_ref(
                    stack, layer, use_raw_codeuri, ignore_code_extraction_warnings
                )
                if found_layer:
                    layers.append(found_layer)
            else:
                LOG.debug(
                    'layer "%s" is not recognizable, '
                    "it might be using intrinsic functions that we don't support yet. Skipping.",
                    str(layer),
                )

        return layers

    @staticmethod
    def _locate_layer_from_ref(
        stack: Stack, layer: Dict, use_raw_codeuri: bool = False, ignore_code_extraction_warnings: bool = False
    ) -> Optional[LayerVersion]:
        layer_logical_id = cast(str, layer.get("Ref"))
        layer_resource = stack.resources.get(layer_logical_id)
        if not layer_resource or layer_resource.get("Type", "") not in (
            SamFunctionProvider.SERVERLESS_LAYER,
            SamFunctionProvider.LAMBDA_LAYER,
        ):
            raise InvalidLayerReference()

        layer_properties = layer_resource.get("Properties", {})
        resource_type = layer_resource.get("Type")
        compatible_runtimes = layer_properties.get("CompatibleRuntimes")
        codeuri: Optional[str] = None

        if resource_type in [SamFunctionProvider.LAMBDA_LAYER, SamFunctionProvider.SERVERLESS_LAYER]:
            code_property_key = SamBaseProvider.CODE_PROPERTY_KEYS[resource_type]
            if SamBaseProvider._is_s3_location(layer_properties.get(code_property_key)):
                # Content can be a dictionary of S3 Bucket/Key or a S3 URI, neither of which are supported
                if not ignore_code_extraction_warnings:
                    SamFunctionProvider._warn_code_extraction(resource_type, layer_logical_id, code_property_key)
                return None
            codeuri = SamBaseProvider._extract_codeuri(layer_properties, code_property_key)

        if codeuri and not use_raw_codeuri:
            LOG.debug("--base-dir is not presented, adjusting uri %s relative to %s", codeuri, stack.location)
            codeuri = SamLocalStackProvider.normalize_resource_path(stack.location, codeuri)

        return LayerVersion(
            layer_logical_id,
            codeuri,
            compatible_runtimes,
            layer_resource.get("Metadata", None),
            stack_path=stack.stack_path,
        )

    def get_resources_by_stack_path(self, stack_path: str) -> Dict:
        candidates = [stack.resources for stack in self.stacks if stack.stack_path == stack_path]
        if not candidates:
            raise RuntimeError(f"Cannot find resources with stack_path = {stack_path}")
        return candidates[0]
