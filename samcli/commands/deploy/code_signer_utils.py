"""
Utilities for code signing process
"""

import logging
from typing import Dict, List, Set

from click import STRING, prompt

from samcli.lib.providers.provider import Stack
from samcli.lib.providers.sam_function_provider import SamFunctionProvider

LOG = logging.getLogger(__name__)


def prompt_profile_name(profile_name, start_bold, end_bold):
    return prompt(f"\t{start_bold}Signing Profile Name{end_bold}", type=STRING, default=profile_name)


def prompt_profile_owner(profile_owner, start_bold, end_bold):
    # click requires to have non None value for passing
    if not profile_owner:
        profile_owner = ""

    profile_owner = prompt(
        f"\t{start_bold}Signing Profile Owner Account ID (optional){end_bold}",
        type=STRING,
        default=profile_owner,
        show_default=len(profile_owner) > 0,
    )

    return profile_owner


def extract_profile_name_and_owner_from_existing(function_or_layer_name, signing_profiles):
    profile_name = None
    profile_owner = None
    # extract any code sign config that is passed via command line
    if function_or_layer_name in signing_profiles:
        profile_name = signing_profiles[function_or_layer_name]["profile_name"]
        profile_owner = signing_profiles[function_or_layer_name]["profile_owner"]

    return profile_name, profile_owner


def signer_config_per_function(stacks: List[Stack]):
    functions_with_code_sign = set()
    layers_with_code_sign: Dict[str, Set[str]] = {}

    sam_functions = SamFunctionProvider(stacks)

    for sam_function in sam_functions.get_all():
        if sam_function.codesign_config_arn:
            function_name = sam_function.name
            LOG.debug("Found the following function with a code signing config %s", function_name)
            functions_with_code_sign.add(function_name)

            if sam_function.layers:
                for layer in sam_function.layers:
                    layer_name = layer.name
                    LOG.debug("Found following layers inside the function %s", layer_name)
                    if layer_name in layers_with_code_sign:
                        layers_with_code_sign[layer_name].add(function_name)
                    else:
                        functions_that_is_referring_to_function = set()
                        functions_that_is_referring_to_function.add(function_name)
                        layers_with_code_sign[layer_name] = functions_that_is_referring_to_function

    return functions_with_code_sign, layers_with_code_sign
