"""
build utilities
"""

import logging
from typing import Dict, Optional, Union

from samcli.commands.local.lib.exceptions import OverridesNotWellDefinedError
from samcli.lib.build.build_graph import LayerBuildDefinition
from samcli.lib.providers.provider import Function, LayerVersion
from samcli.lib.utils.architecture import ARM64, X86_64

LOG = logging.getLogger(__name__)


def valid_architecture(architecture: str) -> bool:
    return architecture in [X86_64, ARM64]


def warn_on_invalid_architecture(layer_definition: LayerBuildDefinition) -> None:
    """
    Validate the BuildArchitecture of a LambdaLayer.

    Prints corresponding LOG warning if something is invalid.
    """
    layer_architecture = layer_definition.architecture
    layer_id = layer_definition.layer.layer_id

    if not valid_architecture(layer_architecture):
        LOG.warning("WARNING: `%s` in Layer `%s` is not a valid architecture.", layer_architecture, layer_id)


def _make_env_vars(
    resource: Union[Function, LayerVersion], file_env_vars: Dict, inline_env_vars: Optional[Dict]
) -> Dict:
    """Returns the environment variables configuration for this function

    Priority order (high to low):
    1. Function specific env vars from command line
    2. Function specific env vars from json file
    3. Global env vars from command line
    4. Global env vars from json file

    Parameters
    ----------
    resource : Union[Function, LayerVersion]
        Lambda function or layer to generate the configuration for
    file_env_vars : Dict
        The dictionary of environment variables loaded from the file
    inline_env_vars : Optional[Dict]
        The optional dictionary of environment variables defined inline

    Returns
    -------
    dictionary
        Environment variable configuration for this function

    Raises
    ------
    samcli.commands.local.lib.exceptions.OverridesNotWellDefinedError
        If the environment dict is in the wrong format to process environment vars

    """

    name = resource.name
    result = {}

    # validate and raise OverridesNotWellDefinedError
    for env_var in list((file_env_vars or {}).values()) + list((inline_env_vars or {}).values()):
        if not isinstance(env_var, dict):
            reason = "Environment variables {} in incorrect format".format(env_var)
            LOG.debug(reason)
            raise OverridesNotWellDefinedError(reason)

    if file_env_vars:
        parameter_result = file_env_vars.get("Parameters", {})
        result.update(parameter_result)

    if inline_env_vars:
        inline_parameter_result = inline_env_vars.get("Parameters", {})
        result.update(inline_parameter_result)

    if file_env_vars:
        specific_result = file_env_vars.get(name, {})
        result.update(specific_result)

    if inline_env_vars:
        inline_specific_result = inline_env_vars.get(name, {})
        result.update(inline_specific_result)

    return result
