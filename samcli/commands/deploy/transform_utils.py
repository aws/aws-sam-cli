"""
Transform for SAM templates to convert into function resource representation.
"""
from samcli.lib.providers.sam_function_provider import SamFunctionProvider


def transform_template(parameter_overrides, template_dict):
    """

    :param parameter_overrides: Dictionary of parameter overrides for the SAM template.
    :param template_dict: Dictionary representation of the SAM template.
    :return:
    """
    sam_functions = SamFunctionProvider(
        template_dict=template_dict, parameter_overrides=parameter_overrides, ignore_code_extraction_warnings=True
    )

    return sam_functions
