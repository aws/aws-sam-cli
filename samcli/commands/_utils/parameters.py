"""
Template parameters utilities shared by various commands
"""

from typing import Dict, Union, Optional


def sanitize_parameter_overrides(
    parameter_overrides: Dict[str, Union[Dict[str, str], str]]
) -> Dict[str, Optional[str]]:
    """
    Get sanitized parameter override values based on if the workflow went via a guided deploy to set the
    parameter overrides for deployment. If a guided deploy was followed the parameter overrides consists
    of additional information such as if a given parameter's value is hidden or not.
    :param parameter_overrides: dictionary of parameter key values.
    :return:
    """
    return {key: value.get("Value") if isinstance(value, dict) else value for key, value in parameter_overrides.items()}
