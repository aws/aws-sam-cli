"""
nested stack manager to generate nested stack information and update original template with it
"""
import logging
import os
from copy import deepcopy
from typing import Dict, Optional, cast

from samcli.commands._utils.template import move_template
from samcli.lib.bootstrap.nested_stack.nested_stack_builder import NestedStackBuilder
from samcli.lib.build.app_builder import ApplicationBuildResult
from samcli.lib.providers.provider import Stack, Function
from samcli.lib.providers.sam_function_provider import SamFunctionProvider
from samcli.lib.utils.packagetype import ZIP
from samcli.lib.utils.resources import AWS_SERVERLESS_FUNCTION, AWS_LAMBDA_FUNCTION

LOG = logging.getLogger(__name__)

# Resource name of the CFN stack
NESTED_STACK_NAME = "AwsSamAutoDependencyLayerNestedStack"

# Resources which we support creating dependency layer
SUPPORTED_RESOURCES = {AWS_SERVERLESS_FUNCTION, AWS_LAMBDA_FUNCTION}

# Languages which we support creating dependency layer
SUPPORTED_LANGUAGES = ("python", "nodejs", "java")


class NestedStackManager:

    _stack_name: str
    _build_dir: str
    _stack_location: str
    _current_template: Dict
    _app_build_result: ApplicationBuildResult
    _nested_stack_builder: NestedStackBuilder

    def __init__(
            self,
            stack_name: str,
            build_dir: str,
            stack_location: str,
            current_template: Dict,
            app_build_result: ApplicationBuildResult
    ):
        """
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
        self._stack_name = stack_name
        self._build_dir = build_dir
        self._stack_location = stack_location
        self._current_template = current_template
        self._app_build_result = app_build_result
        self._nested_stack_builder = NestedStackBuilder()

    def generate_auto_dependency_layer_stack(self) -> Dict:
        """
        Loops through all resources, and for the supported ones (SUPPORTED_RESOURCES and SUPPORTED_LANGUAGES)
        creates layer for its dependencies in a nested stack, and adds reference of the nested stack back to original
        stack
        """
        template = deepcopy(self._current_template)
        resources = template.get("Resources", {})

        stack = Stack("", self._stack_name, self._stack_location, {}, template_dict=template)
        function_provider = SamFunctionProvider([stack], ignore_code_extraction_warnings=True)
        zip_functions = [function for function in function_provider.get_all() if function.packagetype == ZIP]

        for zip_function in zip_functions:
            if not self._is_function_supported(zip_function):
                continue

            dependencies_dir = self._get_dependencies_dir(zip_function)
            if not dependencies_dir:
                LOG.debug(
                    "Dependency folder can't be found for %s, skipping auto dependency layer creation",
                    zip_function.name
                )
                continue

            self._add_layer(dependencies_dir, zip_function, resources)

        if not self._nested_stack_builder.is_any_function_added():
            LOG.debug("No function has been added for auto dependency layer creation")
            return template

        nested_template_location = os.path.join(self._build_dir, "nested_template.yaml")
        move_template(self._stack_location, nested_template_location, self._nested_stack_builder.build_as_dict())

        resources[NESTED_STACK_NAME] = self._nested_stack_builder.get_nested_stack_reference_resource(
            nested_template_location)
        return template

    def _add_layer(self, dependencies_dir: str, function: Function, resources: Dict):
        self._add_layer_readme_info(dependencies_dir, function.name)

        layer_output_key = self._nested_stack_builder.add_function(self._stack_name, dependencies_dir, function)

        # add layer reference back to function
        function_properties = cast(Dict, resources.get(function.name)).get("Properties", {})
        function_layers = function_properties.get("Layers", [])
        function_layers.append({"Fn:GettAtt": [NESTED_STACK_NAME, f"Outputs.{layer_output_key}"]})
        function_properties["Layers"] = function_layers

    @staticmethod
    def _add_layer_readme_info(dependencies_dir: str, function_name: str):
        # add a simple README file for discoverability
        with open(os.path.join(dependencies_dir, "AWS_SAM_CLI_README"), "w+") as f:
            f.write(
                f"This layer contains dependencies of function {function_name} "
                "and automatically added by AWS SAM CLI command 'sam sync'"
            )

    def _is_function_supported(self, function: Function):
        """
        Checks if function is built with current session and its runtime is supported
        """
        # check if function is built
        if function.name not in self._app_build_result.artifacts.keys():
            LOG.debug(
                "Function %s is not built within SAM CLI, skipping for auto dependency layer creation",
                function.name,
            )
            return False

        # check if runtime/language is supported
        if not function.runtime or not function.runtime.startswith(SUPPORTED_LANGUAGES):
            LOG.debug(
                "For function %s, runtime %s is not supported for auto dependency layer creation",
                function.name,
                function.runtime,
            )
            return False

        return True

    def _get_dependencies_dir(self, function: Function) -> Optional[str]:
        """
        Returns dependency directory information for function
        """
        dependencies_dir = None
        for function_build_definition in self._app_build_result.build_graph.get_function_build_definitions():
            for build_definition_function in function_build_definition.functions:
                if build_definition_function.name == function.name:
                    dependencies_dir = function_build_definition.dependencies_dir
                    break

        return dependencies_dir
