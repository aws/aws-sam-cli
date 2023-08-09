"""
Base class for SAM Template providers
"""

import logging
from typing import Any, Dict, Iterable, Optional, Union, cast

from samcli.lib.iac.plugins_interfaces import Stack
from samcli.lib.intrinsic_resolver.intrinsic_property_resolver import IntrinsicResolver
from samcli.lib.intrinsic_resolver.intrinsics_symbol_table import IntrinsicsSymbolTable
from samcli.lib.package.ecr_utils import is_ecr_url
from samcli.lib.samlib.resource_metadata_normalizer import ResourceMetadataNormalizer
from samcli.lib.samlib.wrapper import SamTranslatorWrapper
from samcli.lib.utils.resources import (
    AWS_LAMBDA_FUNCTION,
    AWS_LAMBDA_LAYERVERSION,
    AWS_SERVERLESS_FUNCTION,
    AWS_SERVERLESS_LAYERVERSION,
)

LOG = logging.getLogger(__name__)


class SamBaseProvider:
    """
    Base class for SAM Template providers
    """

    DEFAULT_CODEURI = "."

    CODE_PROPERTY_KEYS = {
        AWS_LAMBDA_FUNCTION: "Code",
        AWS_SERVERLESS_FUNCTION: "CodeUri",
        AWS_LAMBDA_LAYERVERSION: "Content",
        AWS_SERVERLESS_LAYERVERSION: "ContentUri",
    }

    IMAGE_PROPERTY_KEYS = {
        AWS_LAMBDA_FUNCTION: "Code",
        AWS_SERVERLESS_FUNCTION: "ImageUri",
    }

    def get(self, name: str) -> Optional[Any]:
        """
        Given name of the function, this method must return the Function object

        :param string name: Name of the function
        :return Function: namedtuple containing the Function information
        """
        raise NotImplementedError("not implemented")

    def get_all(self) -> Iterable:
        """
        Yields all the Lambda functions available in the provider.

        :yields Function: namedtuple containing the function information
        """
        raise NotImplementedError("not implemented")

    @staticmethod
    def _extract_codeuri(resource_properties: Dict, code_property_key: str) -> str:
        """
        Extracts the Function/Layer code path from the Resource Properties

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
        codeuri = resource_properties.get(code_property_key, SamBaseProvider.DEFAULT_CODEURI)

        if isinstance(codeuri, dict):
            return SamBaseProvider.DEFAULT_CODEURI

        return cast(str, codeuri)

    @staticmethod
    def _is_s3_location(location: Optional[Union[str, Dict]]) -> bool:
        """
        the input could be:
        - CodeUri of Serverless::Function
        - Code of Lambda::Function
        - ContentUri of Serverless::LayerVersion
        - Content of Lambda::LayerVersion
        """
        return (isinstance(location, dict) and ("S3Bucket" in location or "Bucket" in location)) or (
            isinstance(location, str) and location.startswith("s3://")
        )

    @staticmethod
    def _is_ecr_uri(location: Optional[Union[str, Dict]]) -> bool:
        """
        the input could be:
        - ImageUri of Serverless::Function
        - Code of Lambda::Function
        """
        return location is not None and is_ecr_url(
            str(location.get("ImageUri", "")) if isinstance(location, dict) else location
        )

    @staticmethod
    def _warn_code_extraction(resource_type: str, resource_name: str, code_property: str) -> None:
        LOG.warning(
            "The resource %s '%s' has specified S3 location for %s. "
            "It will not be built and SAM CLI does not support invoking it locally.",
            resource_type,
            resource_name,
            code_property,
        )

    @staticmethod
    def _warn_imageuri_extraction(resource_type: str, resource_name: str, image_property: str) -> None:
        LOG.warning(
            "The resource %s '%s' has specified ECR registry image for %s. "
            "It will not be built and SAM CLI does not support invoking it locally.",
            resource_type,
            resource_name,
            image_property,
        )

    @staticmethod
    def _extract_lambda_function_imageuri(resource_properties: Dict, code_property_key: str) -> Optional[str]:
        """
        Extracts the Lambda Function ImageUri from the Resource Properties

        Parameters
        ----------
        resource_properties dict
            Dictionary representing the Properties of the Resource
        code_property_key str
            Property Key of the code on the Resource

        Returns
        -------
        str
            Representing the local imageuri
        """
        return cast(Optional[str], resource_properties.get(code_property_key, dict()).get("ImageUri", None))

    @staticmethod
    def _extract_sam_function_imageuri(resource_properties: Dict, code_property_key: str) -> Optional[str]:
        """
        Extracts the Serverless Function ImageUri from the Resource Properties

        Parameters
        ----------
        resource_properties dict
            Dictionary representing the Properties of the Resource
        code_property_key str
            Property Key of the code on the Resource

        Returns
        -------
        str
            Representing the local imageuri
        """
        return resource_properties.get(code_property_key, None)

    @staticmethod
    def get_template(
        template_dict: Dict, parameter_overrides: Optional[Dict[str, str]] = None, use_sam_transform: bool = True
    ) -> Dict:
        """
        Given a SAM template dictionary, return a cleaned copy of the template where SAM plugins have been run
        and parameter values have been substituted.

        Parameters
        ----------
        template_dict : dict
            unprocessed SAM template dictionary

        parameter_overrides: dict
            Optional dictionary of values for template parameters

        use_sam_transform: bool
            Whether to transform the given template with Serverless Application Model. Default is True

        Returns
        -------
        dict
            Processed SAM template
        """
        template_dict = template_dict or {}
        parameters_values = SamBaseProvider._get_parameter_values(template_dict, parameter_overrides)
        if template_dict and use_sam_transform:
            template_dict = SamTranslatorWrapper(template_dict, parameter_values=parameters_values).run_plugins()
        ResourceMetadataNormalizer.normalize(template_dict)

        resolver = IntrinsicResolver(
            template=template_dict,
            symbol_resolver=IntrinsicsSymbolTable(logical_id_translator=parameters_values, template=template_dict),
        )
        template_dict = resolver.resolve_template(ignore_errors=True)
        return template_dict

    @staticmethod
    def get_resolved_template_dict(
        template_dict: Stack,
        parameter_overrides: Optional[Dict[str, str]] = None,
        normalize_resource_metadata: bool = True,
    ) -> Stack:
        """
        Given a SAM template dictionary, return a cleaned copy of the template where SAM plugins have been run
        and parameter values have been substituted.
        Parameters
        ----------
        template_dict : dict
            unprocessed SAM template dictionary
        parameter_overrides: dict
            Optional dictionary of values for template parameters
        normalize_resource_metadata: bool
            flag to normalize resource metadata or not; For package and deploy, we don't need to normalize resource
            metadata, which usually exists in a CDK-synthed template and is used for build and local testing
        Returns
        -------
        dict
            Processed SAM template
            :param template_dict:
            :param parameter_overrides:
            :param normalize_resource_metadata:
        """
        template_dict = template_dict or Stack()
        parameters_values = SamBaseProvider._get_parameter_values(template_dict, parameter_overrides)
        if template_dict:
            template_dict = SamTranslatorWrapper(template_dict, parameter_values=parameters_values).run_plugins()
        if normalize_resource_metadata:
            ResourceMetadataNormalizer.normalize(template_dict)

        resolver = IntrinsicResolver(
            template=template_dict,
            symbol_resolver=IntrinsicsSymbolTable(logical_id_translator=parameters_values, template=template_dict),
        )
        template_dict = resolver.resolve_template(ignore_errors=True)
        return template_dict

    @staticmethod
    def _get_parameter_values(template_dict: Any, parameter_overrides: Optional[Dict]) -> Dict:
        """
        Construct a final list of values for CloudFormation template parameters based on user-supplied values,
        default values provided in template, and sane defaults for pseudo-parameters.

        Parameters
        ----------
        template_dict : dict
            SAM template dictionary

        parameter_overrides : dict
            User-supplied values for CloudFormation template parameters

        Returns
        -------
        dict
            Values for template parameters to substitute in template with
        """

        default_values = SamBaseProvider._get_default_parameter_values(template_dict)

        # NOTE: Ordering of following statements is important. It makes sure that any user-supplied values
        # override the defaults
        parameter_values = {}
        parameter_values.update(IntrinsicsSymbolTable.DEFAULT_PSEUDO_PARAM_VALUES)
        parameter_values.update(default_values)
        parameter_values.update(parameter_overrides or {})

        return parameter_values

    @staticmethod
    def _get_default_parameter_values(sam_template: Dict) -> Dict:
        """
        Method to read default values for template parameters and return it
        Example:
        If the template contains the following parameters defined
        Parameters:
            Param1:
                Type: String
                Default: default_value1
            Param2:
                Type: String
                Default: default_value2

        then, this method will grab default value for Param1 and return the following result:
        {
            Param1: "default_value1",
            Param2: "default_value2"
        }
        :param dict sam_template: SAM template
        :return dict: Default values for parameters
        """

        default_values: Dict = {}

        parameter_definition = sam_template.get("Parameters", None)
        if not parameter_definition or not isinstance(parameter_definition, dict):
            LOG.debug("No Parameters detected in the template")
            return default_values

        for param_name, value in parameter_definition.items():
            if isinstance(value, dict) and "Default" in value:
                default_values[param_name] = value["Default"]

        LOG.debug("Collected default values for parameters: %s", default_values)
        return default_values
