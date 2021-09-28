"""
nested stack manager to generate nested stack information and update original template with it
"""
import logging
import os
from copy import deepcopy
from typing import Dict, cast

from samcli.commands._utils.template import move_template
from samcli.lib.bootstrap.nested_stack.nested_stack_builder import NestedStackBuilder
from samcli.lib.build.app_builder import ApplicationBuildResult
from samcli.lib.providers.provider import Stack
from samcli.lib.providers.sam_function_provider import SamFunctionProvider
from samcli.lib.utils.packagetype import ZIP
from samcli.lib.utils.resources import AWS_SERVERLESS_FUNCTION, AWS_LAMBDA_FUNCTION

LOG = logging.getLogger(__name__)

# Resource name of the CFN stack
NESTED_STACK_NAME = "AwsSamAutoDependencyLayerNestedStack"

# Resources which we support creating dependency layer
SUPPORTED_RESOURCES = {AWS_SERVERLESS_FUNCTION, AWS_LAMBDA_FUNCTION}

# Languages which we support creating dependency layer
SUPPORTED_LANGUAGES = {"python", "nodejs", "java"}


def generate_auto_dependency_layer_stack(
    stack_name: str,
    build_dir: str,
    stack_location: str,
    current_template: Dict,
    app_build_result: ApplicationBuildResult,
) -> Dict:
    """
    Loops through all resources, and for the supported ones (SUPPORTED_RESOURCES and SUPPORTED_LANGUAGES)
    creates layer for its dependencies in a nested stack, and adds reference of the nested stack back to original
    stack

    Parameters
    ----------
    stack_name : str
        Original stack name, which is used to generate layer name
    build_dir : str
        Build directory for storing the new nested stack template
    stack_location : str
        Used to move template and its resources' relative path information
    current_template : Dict
        Current template of the project
    app_build_result: ApplicationBuildResult
        Application build result, which contains build graph, and built artifacts information
    """
    template = deepcopy(current_template)
    resources = template.get("Resources", {})
    artifacts = app_build_result.artifacts
    nested_stack_builder = NestedStackBuilder()

    stack = Stack("", stack_name, stack_location, {}, template_dict=template)
    function_provider = SamFunctionProvider([stack], ignore_code_extraction_warnings=True)
    zip_functions = [function for function in function_provider.get_all() if function.packagetype == ZIP]

    for zip_function in zip_functions:
        if zip_function.name not in artifacts.keys():
            LOG.debug(
                "Function %s is not built within SAM CLI, skipping for auto dependency layer creation",
                zip_function.name,
            )
            continue

        # check if runtime/language is supported
        is_runtime_supported = False
        for supported_language in SUPPORTED_LANGUAGES:
            if cast(str, zip_function.runtime).startswith(supported_language):
                is_runtime_supported = True
                break

        if not is_runtime_supported:
            LOG.debug(
                "For function %s, runtime %s is not supported for auto dependency layer creation",
                zip_function.name,
                zip_function.runtime,
            )
            continue

        dependencies_dir = None
        for function_build_definition in app_build_result.build_graph.get_function_build_definitions():
            for function in function_build_definition.functions:
                if zip_function.name == function.name:
                    dependencies_dir = function_build_definition.dependencies_dir
                    break

        if not dependencies_dir:
            LOG.debug(
                "Dependency folder can't be found for %s, skipping auto dependency layer creation", zip_function.name
            )
            continue

        # add a simple README file for discoverability
        with open(os.path.join(dependencies_dir, "AWS_SAM_CLI_README"), "w+") as f:
            f.write(
                f"This layer contains dependencies of function {zip_function.name} "
                "and automatically added by 'sam sync'"
            )

        layer_output_key = nested_stack_builder.add_function(stack_name, dependencies_dir, zip_function)

        # add layer reference back to function
        function_properties = resources.get(zip_function.name).get("Properties", {})
        function_layers = function_properties.get("Layers", [])
        function_layers.append({"Fn:GettAtt": [NESTED_STACK_NAME, f"Outputs.{layer_output_key}"]})
        function_properties["Layers"] = function_layers

    if not nested_stack_builder.is_any_function_added():
        LOG.debug("No function has been added for auto dependency layer creation")
        return template

    nested_template_location = os.path.join(build_dir, "nested_template.yaml")
    move_template(stack_location, nested_template_location, nested_stack_builder.build_as_dict())

    resources[NESTED_STACK_NAME] = nested_stack_builder.get_nested_stack_reference_resource(nested_template_location)
    return template
