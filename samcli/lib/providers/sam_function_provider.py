"""
Class that provides functions from a given SAM template
"""
import logging
from typing import Dict, List, Optional, cast, Iterator, Any

from samtranslator.policy_template_processor.exceptions import TemplateNotFoundException

from samcli.lib.utils.resources import (
    AWS_LAMBDA_FUNCTION,
    AWS_LAMBDA_LAYERVERSION,
    AWS_SERVERLESS_FUNCTION,
    AWS_SERVERLESS_LAYERVERSION,
)
from samcli.commands.local.cli_common.user_exceptions import InvalidLayerVersionArn
from samcli.commands._utils.template import TemplateFailedParsingException
from samcli.lib.providers.exceptions import InvalidLayerReference
from samcli.lib.utils.colors import Colored
from samcli.lib.utils.packagetype import ZIP, IMAGE
from samcli.lib.utils.file_observer import FileObserver
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

        self._stacks = stacks

        for stack in stacks:
            LOG.debug("%d resources found in the stack %s", len(stack.resources), stack.stack_path)

        # Store a map of function full_path to function information for quick reference
        self.functions = SamFunctionProvider._extract_functions(
            self._stacks, use_raw_codeuri, ignore_code_extraction_warnings
        )

        self._deprecated_runtimes = {"nodejs4.3", "nodejs6.10", "nodejs8.10", "dotnetcore2.0"}
        self._colored = Colored()

    @property
    def stacks(self) -> List[Stack]:
        """
        Returns the list of stacks (including the root stack and all children stacks)

        :return list: list of stacks
        """
        return self._stacks

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

        resolved_function = None

        if name in self.functions:
            # support lookup by full_path
            resolved_function = self.functions.get(name)

        if not resolved_function:
            # If function is not found by full path, search through all functions

            found_fs = []

            for f in self.get_all():
                if name in (f.function_id, f.name, f.functionname):
                    found_fs.append(f)

            # If multiple functions are found, only return one of them
            if len(found_fs) > 1:
                found_fs.sort(key=lambda f0: f0.full_path.lower())

                message = (
                    f"Multiple functions found with keyword {name}! Function {found_fs[0].full_path} will be "
                    f"invoked! If it's not the function you are going to invoke, please choose one of them from"
                    f" below:"
                )
                LOG.warning(Colored().yellow(message))

                for found_f in found_fs:
                    LOG.warning(Colored().yellow(found_f.full_path))

                resolved_function = found_fs[0]

            elif len(found_fs) == 1:
                resolved_function = found_fs[0]

        if resolved_function:
            self._deprecate_notification(resolved_function.runtime)

        return resolved_function

    def _deprecate_notification(self, runtime: Optional[str]) -> None:
        if runtime in self._deprecated_runtimes:
            message = (
                f"WARNING: {runtime} is no longer supported by AWS Lambda, "
                "please update to a newer supported runtime. SAM CLI "
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

                if resource_type in [AWS_SERVERLESS_FUNCTION, AWS_LAMBDA_FUNCTION]:
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

                    if (
                        resource_package_type == IMAGE
                        and SamBaseProvider._is_ecr_uri(resource_properties.get(image_property_key))
                        and not SamFunctionProvider._metadata_has_necessary_entries_for_image_function_to_be_built(
                            resource_metadata
                        )
                    ):
                        # ImageUri can be an ECR uri, which is not supported
                        if not ignore_code_extraction_warnings:
                            SamFunctionProvider._warn_imageuri_extraction(resource_type, name, image_property_key)
                        continue

                if resource_type == AWS_SERVERLESS_FUNCTION:
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

                elif resource_type == AWS_LAMBDA_FUNCTION:
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
        function_id = SamFunctionProvider._get_function_id(resource_properties, name)
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
            stack, function_id, name, codeuri, resource_properties, layers, inlinecode, imageuri, use_raw_codeuri
        )

    @staticmethod
    def _get_function_id(resource_properties: Dict, logical_id: str) -> str:
        """
        Get unique id for Function resource.
        For CFN/SAM project, this function id is the logical id.
        For CDK project, this function id is the user-defined resource id, or the logical id if the resource id is not
        found.

        Parameters
        ----------
        resource_properties str
            Properties of this resource
        logical_id str
            LogicalID of the resource

        Returns
        -------
        str
            The unique function id
        """
        function_id = resource_properties.get("Metadata", {}).get("SamResourceId")
        if isinstance(function_id, str) and function_id:
            return function_id

        return logical_id

    @staticmethod
    def _convert_lambda_function_resource(
        stack: Stack,
        name: str,
        resource_properties: Dict,
        layers: List[LayerVersion],
        use_raw_codeuri: bool = False,
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
        function_id = SamFunctionProvider._get_function_id(resource_properties, name)
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
            stack, function_id, name, codeuri, resource_properties, layers, inlinecode, imageuri, use_raw_codeuri
        )

    @staticmethod
    def _build_function_configuration(
        stack: Stack,
        function_id: str,
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
        function_id str
            Unique function id
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
            function_id=function_id,
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
            architectures=resource_properties.get("Architectures", None),
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
            AWS_SERVERLESS_LAYERVERSION,
            AWS_LAMBDA_LAYERVERSION,
        ):
            raise InvalidLayerReference()

        layer_properties = layer_resource.get("Properties", {})
        resource_type = layer_resource.get("Type")
        compatible_runtimes = layer_properties.get("CompatibleRuntimes")
        codeuri: Optional[str] = None

        if resource_type in [AWS_LAMBDA_LAYERVERSION, AWS_SERVERLESS_LAYERVERSION]:
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
        candidates = [stack.resources for stack in self._stacks if stack.stack_path == stack_path]
        if not candidates:
            raise RuntimeError(f"Cannot find resources with stack_path = {stack_path}")
        return candidates[0]

    @staticmethod
    def _metadata_has_necessary_entries_for_image_function_to_be_built(metadata: Optional[Dict[str, Any]]) -> bool:
        """
        > Note: If the PackageType property is set to Image, then either ImageUri is required,
          or you must build your application with necessary Metadata entries in the AWS SAM template file.
          https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-resource-function.html#sam-function-imageuri

        When ImageUri and Metadata are both provided, we will try to determine whether to treat the function
        as to be built or to be skipped. When we skip it whenever "ImageUri" is provided,
        we introduced a breaking change https://github.com/aws/aws-sam-cli/issues/3239

        This function is used to check whether there are the customers have "intention" to
        let AWS SAM CLI to build this image function.
        """
        return isinstance(metadata, dict) and bool(metadata.get("DockerContext"))


class RefreshableSamFunctionProvider(SamFunctionProvider):
    """
    Fetches and returns Lambda Functions from a SAM Template. The SAM template passed to this provider is assumed
    to be valid, normalized and a dictionary. It also detects any stack template change, and refreshes the loaded
    functions.

    It may or may not contain a function.
    """

    def __init__(
        self,
        stacks: List[Stack],
        parameter_overrides: Optional[Dict] = None,
        global_parameter_overrides: Optional[Dict] = None,
        use_raw_codeuri: bool = False,
        ignore_code_extraction_warnings: bool = False,
    ) -> None:
        """
        Initialize the class with SAM template data. The SAM template passed to this provider is assumed
        to be valid, normalized and a dictionary. It should be normalized by running all pre-processing
        before passing to this class. The process of normalization will remove structures like ``Globals``, resolve
        intrinsic functions etc.
        This class does not perform any syntactic validation of the template.

        This Class will also initialize watchers, to check the stack templates for any update, and refresh the loaded
        functions.

        :param dict stacks: List of stacks functions are extracted from
        :param bool use_raw_codeuri: Do not resolve adjust core_uri based on the template path, use the raw uri.
            Note(xinhol): use_raw_codeuri is temporary to fix a bug, and will be removed for a permanent solution.
        :param bool ignore_code_extraction_warnings: Ignores Log warnings
        """

        super().__init__(stacks, use_raw_codeuri, ignore_code_extraction_warnings)

        # initialize root templates. Usually it will be one template, as sam commands only support processing
        # one template. These templates will be fixed.
        self._use_raw_codeuri = use_raw_codeuri
        self._ignore_code_extraction_warnings = ignore_code_extraction_warnings
        self._parameter_overrides = parameter_overrides
        self._global_parameter_overrides = global_parameter_overrides
        self.parent_templates_paths = []
        for stack in self._stacks:
            if stack.is_root_stack:
                self.parent_templates_paths.append(stack.location)

        self.is_changed = False
        self._observer = FileObserver(self._set_templates_changed)
        self._observer.start()
        self._watch_stack_templates(stacks)

    @property
    def stacks(self) -> List[Stack]:
        """
        It Checks if any template got changed, then refresh the loaded stacks, and functions.

        Returns the list of stacks (including the root stack and all children stacks)

        :return list: list of stacks
        """
        if self.is_changed:
            self._refresh_loaded_functions()

        return super().stacks

    def get(self, name: str) -> Optional[Function]:
        """
        It Checks if any template got changed, then refresh the loaded functions before finding the required function.

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

        if self.is_changed:
            self._refresh_loaded_functions()

        return super().get(name)

    def get_all(self) -> Iterator[Function]:
        """
        It Checks if any template got changed, then refresh the loaded functions before returning all available
        functions.

        Yields all the Lambda functions available in the SAM Template.

        :yields Function: namedtuple containing the function information
        """

        if self.is_changed:
            self._refresh_loaded_functions()

        return super().get_all()

    def get_resources_by_stack_path(self, stack_path: str) -> Dict:
        if self.is_changed:
            self._refresh_loaded_functions()
        return super().get_resources_by_stack_path(stack_path)

    def _set_templates_changed(self, paths: List[str]) -> None:
        LOG.info(
            "A change got detected in the templates %s. Mark templates as changed to be reloaded in the next invoke",
            ", ".join(paths),
        )
        self.is_changed = True
        for stack in self._stacks:
            self._observer.unwatch(stack.location)

    def _watch_stack_templates(self, stacks: List[Stack]) -> None:
        """
        initialize the list of stack template watchers
        """
        for stack in stacks:
            self._observer.watch(stack.location)

    def _refresh_loaded_functions(self) -> None:
        """
        Reload the stacks, and lambda functions from template files.
        """
        LOG.debug("A change got detected in one of the stack templates. Reload the lambda function resources")
        self._stacks = []

        for template_file in self.parent_templates_paths:
            try:
                template_stacks, _ = SamLocalStackProvider.get_stacks(
                    template_file,
                    parameter_overrides=self._parameter_overrides,
                    global_parameter_overrides=self._global_parameter_overrides,
                )
                self._stacks += template_stacks
            except (TemplateNotFoundException, TemplateFailedParsingException) as ex:
                raise ex

        self.is_changed = False
        self.functions = self._extract_functions(
            self._stacks, self._use_raw_codeuri, self._ignore_code_extraction_warnings
        )
        self._watch_stack_templates(self._stacks)

    def stop_observer(self) -> None:
        """
        Stop Observing.
        """
        self._observer.stop()
