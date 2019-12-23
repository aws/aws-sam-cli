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
        if template_dict:
            template_dict = SamTranslatorWrapper(template_dict).run_plugins()
        ResourceMetadataNormalizer.normalize(template_dict)
        logical_id_translator = SamBaseProvider._get_parameter_values(template_dict, parameter_overrides)

        resolver = IntrinsicResolver(
            template=template_dict,
            symbol_resolver=IntrinsicsSymbolTable(logical_id_translator=logical_id_translator, template=template_dict),
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
