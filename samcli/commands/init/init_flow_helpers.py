"""
Init flow based helper functions
"""
import functools
import logging
import re
from typing import Optional

from samcli.lib.utils.architecture import X86_64
from samcli.local.common.runtime_template import INIT_RUNTIMES, LAMBDA_IMAGES_RUNTIMES_MAP, is_custom_runtime

LOG = logging.getLogger(__name__)


def get_sorted_runtimes(runtime_option_list):
    """
    Return a list of sorted runtimes in ascending order of runtime names and
    descending order of runtime version.

    Parameters
    ----------
    runtime_option_list : list
        list of possible runtime to be selected

    Returns
    -------
    list
        sorted list of possible runtime to be selected
    """
    supported_runtime_list = get_supported_runtime(runtime_option_list)
    return sorted(supported_runtime_list, key=functools.cmp_to_key(compare_runtimes))


def get_supported_runtime(runtime_list):
    """
    Returns a list of only runtimes supported by the current version of SAMCLI.
    This is the list that is presented to the customer to select from.

    Parameters
    ----------
    runtime_list : list
        List of runtime

    Returns
    -------
    list
        List of supported runtime
    """
    supported_runtime_list = []
    error_message = ""
    for runtime in runtime_list:
        if runtime not in INIT_RUNTIMES and not is_custom_runtime(runtime):
            if not error_message:
                error_message = "Additional runtimes may be available in the latest SAM CLI version. \
                    Upgrade your SAM CLI to see the full list."
                LOG.debug(error_message)
            continue
        supported_runtime_list.append(runtime)

    return supported_runtime_list


def compare_runtimes(first_runtime, second_runtime):
    """
    Logic to compare supported runtime for sorting.

    Parameters
    ----------
    first_runtime : str
        runtime to be compared
    second_runtime : str
        runtime to be compared

    Returns
    -------
    int
        comparison result
    """

    first_runtime_name, first_version_number = _split_runtime(first_runtime)
    second_runtime_name, second_version_number = _split_runtime(second_runtime)

    if first_runtime_name == second_runtime_name:
        if first_version_number == second_version_number:
            # If it's the same runtime and version return al2 first
            return -1 if first_runtime.endswith(".al2") else 1
        return second_version_number - first_version_number

    return 1 if first_runtime_name > second_runtime_name else -1


def _split_runtime(runtime):
    """
    Split a runtime into its name and version number.

    Parameters
    ----------
    runtime : str
        Runtime in the format supported by Lambda

    Returns
    -------
    (str, float)
        Tuple of runtime name and runtime version
    """
    return (_get_runtime_name(runtime), _get_version_number(runtime))


def _get_runtime_name(runtime):
    """
    Return the runtime name without the version

    Parameters
    ----------
    runtime : str
        Runtime in the format supported by Lambda.

    Returns
    -------
    str
        Runtime name, which is obtained as everything before the first number
    """
    return re.split(r"\d", runtime)[0]


def _get_version_number(runtime):
    """
    Return the runtime version number

    Parameters
    ----------
    runtime_version : str
        version of a runtime

    Returns
    -------
    float
        Runtime version number
    """

    if is_custom_runtime(runtime):
        return 1.0
    return float(re.search(r"\d+(\.\d+)?", runtime).group())


def _get_templates_with_dependency_manager(templates_options, dependency_manager):
    return [t for t in templates_options if t.get("dependencyManager") == dependency_manager]


def _get_runtime_from_image(image: str) -> Optional[str]:
    """
    Get corresponding runtime from the base-image parameter

    Expecting 'amazon/{runtime}-base'
    But might also be like 'amazon/{runtime}-provided.al2-base'
    """
    match = re.fullmatch(r"amazon/([a-z0-9.]*)-?([a-z0-9.]*)-base", image)
    if match is None:
        return None
    runtime, base = match.groups()
    if base:
        return f"{runtime} ({base})"
    return runtime


def _get_image_from_runtime(runtime):
    """
    Get corresponding base-image from the runtime parameter
    """
    return LAMBDA_IMAGES_RUNTIMES_MAP[runtime]


def get_architectures(architecture):
    """
    Returns list of architecture value based on the init input value
    """
    return [X86_64] if architecture is None else [architecture]
