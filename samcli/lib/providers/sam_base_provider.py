"""
Base class for SAM Template providers
"""

import logging

from samcli.lib.intrinsic_resolver.intrinsic_property_resolver import IntrinsicResolver
from samcli.lib.intrinsic_resolver.intrinsics_symbol_table import IntrinsicsSymbolTable
from samcli.lib.samlib.resource_metadata_normalizer import ResourceMetadataNormalizer
from samcli.lib.samlib.wrapper import SamTranslatorWrapper

LOG = logging.getLogger(__name__)


class SamBaseProvider:
    """
    Base class for SAM Template providers
    """

    SERVERLESS_FUNCTION = "AWS::Serverless::Function"
    LAMBDA_FUNCTION = "AWS::Lambda::Function"
    SERVERLESS_LAYER = "AWS::Serverless::LayerVersion"
    LAMBDA_LAYER = "AWS::Lambda::LayerVersion"
    DEFAULT_CODEURI = "."

    def get(self, name):
        """
        Given name of the function, this method must return the Function object

        :param string name: Name of the function
        :return Function: namedtuple containing the Function information
        """
        raise NotImplementedError("not implemented")

    def get_all(self):
        """
        Yields all the Lambda functions available in the provider.

        :yields Function: namedtuple containing the function information
        """
        raise NotImplementedError("not implemented")

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

        codeuri = resource_properties.get(code_property_key, SamBaseProvider.DEFAULT_CODEURI)

        if isinstance(codeuri, dict):
            codeuri = SamBaseProvider.DEFAULT_CODEURI

        return codeuri

    @staticmethod
    def _extract_lambda_function_imageuri(resource_properties, code_property_key):
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
        return resource_properties.get(code_property_key, dict()).get("ImageUri", None)

    @staticmethod
    def _extract_sam_function_imageuri(resource_properties, code_property_key):
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
    def _extract_sam_function_codeuri(
        name, resource_properties, code_property_key, ignore_code_extraction_warnings=False
    ):
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
        ignore_code_extraction_warnings
            Boolean to ignore log statements on code extraction from Resources.

        Returns
        -------
        str
            Representing the local code path
        """
        codeuri = resource_properties.get(code_property_key, SamBaseProvider.DEFAULT_CODEURI)
        # CodeUri can be a dictionary of S3 Bucket/Key or a S3 URI, neither of which are supported
        if isinstance(codeuri, dict) or (isinstance(codeuri, str) and codeuri.startswith("s3://")):
            codeuri = SamBaseProvider.DEFAULT_CODEURI
            if not ignore_code_extraction_warnings:
                LOG.warning(
                    "Lambda function '%s' has specified S3 location for CodeUri which is unsupported. "
                    "Using default value of '%s' instead",
                    name,
                    codeuri,
                )
        return codeuri

    @staticmethod
    def get_template(template_dict, parameter_overrides=None):
        """
        Given a SAM template dictionary, return a cleaned copy of the template where SAM plugins have been run
        and parameter values have been substituted.

        Parameters
        ----------
        template_dict : dict
            unprocessed SAM template dictionary

        parameter_overrides: dict
            Optional dictionary of values for template parameters

        Returns
        -------
        dict
            Processed SAM template
        """
        template_dict = template_dict or {}
        parameters_values = SamBaseProvider._get_parameter_values(template_dict, parameter_overrides)
        if template_dict:
            template_dict = SamTranslatorWrapper(template_dict, parameter_values=parameters_values).run_plugins()
        ResourceMetadataNormalizer.normalize(template_dict)

        resolver = IntrinsicResolver(
            template=template_dict,
            symbol_resolver=IntrinsicsSymbolTable(logical_id_translator=parameters_values, template=template_dict),
        )
        template_dict = resolver.resolve_template(ignore_errors=True)
        return template_dict

    @staticmethod
    def _get_parameter_values(template_dict, parameter_overrides):
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
    def _get_default_parameter_values(sam_template):
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

        default_values = {}

        parameter_definition = sam_template.get("Parameters", None)
        if not parameter_definition or not isinstance(parameter_definition, dict):
            LOG.debug("No Parameters detected in the template")
            return default_values

        for param_name, value in parameter_definition.items():
            if isinstance(value, dict) and "Default" in value:
                default_values[param_name] = value["Default"]

        LOG.debug("Collected default values for parameters: %s", default_values)
        return default_values
