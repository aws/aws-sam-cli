"""
Base class for SAM Template providers
"""

import logging

from samtranslator.intrinsics.resolver import IntrinsicsResolver
from samtranslator.intrinsics.actions import RefAction

from samcli.lib.samlib.wrapper import SamTranslatorWrapper
from samcli.lib.samlib.resource_metadata_normalizer import ResourceMetadataNormalizer


LOG = logging.getLogger(__name__)


class SamBaseProvider(object):
    """
    Base class for SAM Template providers
    """

    # There is not much benefit in infering real values for these parameters in local development context. These values
    # are usually representative of an AWS environment and stack, but in local development scenario they don't make
    # sense. If customers choose to, they can always override this value through the CLI interface.
    _DEFAULT_PSEUDO_PARAM_VALUES = {
        "AWS::AccountId": "123456789012",
        "AWS::Partition": "aws",

        "AWS::Region": "us-east-1",

        "AWS::StackName": "local",
        "AWS::StackId": "arn:aws:cloudformation:us-east-1:123456789012:stack/"
                        "local/51af3dc0-da77-11e4-872e-1234567db123",
        "AWS::URLSuffix": "localhost"
    }

    # Only Ref is supported when resolving template parameters
    _SUPPORTED_INTRINSICS = [RefAction]

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

        template_dict = SamBaseProvider._resolve_parameters(template_dict, parameter_overrides)
        ResourceMetadataNormalizer.normalize(template_dict)
        return template_dict

    @staticmethod
    def _resolve_parameters(template_dict, parameter_overrides):
        """
        In the given template, apply parameter values to resolve intrinsic functions

        Parameters
        ----------
        template_dict : dict
            SAM Template

        parameter_overrides : dict
            Values for template parameters provided by user

        Returns
        -------
        dict
            Resolved SAM template
        """

        parameter_values = SamBaseProvider._get_parameter_values(template_dict, parameter_overrides)

        supported_intrinsics = {action.intrinsic_name: action() for action in SamBaseProvider._SUPPORTED_INTRINSICS}

        # Intrinsics resolver will mutate the original template
        return IntrinsicsResolver(parameters=parameter_values, supported_intrinsics=supported_intrinsics)\
            .resolve_parameter_refs(template_dict)

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
        parameter_values.update(SamBaseProvider._DEFAULT_PSEUDO_PARAM_VALUES)
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
