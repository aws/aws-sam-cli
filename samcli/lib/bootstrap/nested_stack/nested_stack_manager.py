"""
nested stack manager to generate nested stack information and update original template with it
"""
import logging
import os
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Dict, Optional, cast

from samcli.commands._utils.template import move_template
from samcli.lib.bootstrap.nested_stack.nested_stack_builder import NestedStackBuilder
from samcli.lib.build.app_builder import ApplicationBuildResult
from samcli.lib.build.workflow_config import get_layer_subfolder
from samcli.lib.providers.provider import Stack, Function
from samcli.lib.providers.sam_function_provider import SamFunctionProvider
from samcli.lib.sync.exceptions import InvalidRuntimeDefinitionForFunction
from samcli.lib.utils import osutils
from samcli.lib.utils.osutils import BUILD_DIR_PERMISSIONS
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

    _stack: Stack
    _stack_name: str
    _build_dir: str
    _stack_location: str
    _current_template: Dict
    _app_build_result: ApplicationBuildResult
    _nested_stack_builder: NestedStackBuilder

    def __init__(
        self,
        stack: Stack,
        stack_name: str,
        build_dir: str,
        current_template: Dict,
        app_build_result: ApplicationBuildResult,
        stack_metadata: Optional[Dict] = None,
    ):
        """
        Parameters
        ----------
        stack: Stack
            Stack that it is currently been processed
        stack_name : str
            Original stack name, which is used to generate layer name
        build_dir : str
            Build directory for storing the new nested stack template
        current_template : Dict
            Current template of the project
        app_build_result: ApplicationBuildResult
            Application build result, which contains build graph, and built artifacts information
        stack_metadata: Optional[Dict]
            The nested stack resource metadata values.
        """
        self._stack = stack
        self._stack_name = stack_name
        self._build_dir = build_dir
        self._current_template = current_template
        self._app_build_result = app_build_result
        self._nested_stack_builder = NestedStackBuilder()
        self._stack_metadata = stack_metadata if stack_metadata else {}

    def generate_auto_dependency_layer_stack(self) -> Dict:
        """
        Loops through all resources, and for the supported ones (SUPPORTED_RESOURCES and SUPPORTED_LANGUAGES)
        creates layer for its dependencies in a nested stack, and adds reference of the nested stack back to original
        stack
        """
        template = deepcopy(self._current_template)
        resources = template.get("Resources", {})

        function_provider = SamFunctionProvider([self._stack], ignore_code_extraction_warnings=True)
        zip_functions = [function for function in function_provider.get_all() if function.packagetype == ZIP]

        for zip_function in zip_functions:
            if not self._is_function_supported(zip_function):
                continue

            dependencies_dir = self._get_dependencies_dir(zip_function.full_path)
            if not dependencies_dir:
                LOG.debug(
                    "Dependency folder can't be found for %s, skipping auto dependency layer creation",
                    zip_function.full_path,
                )
                continue

            self._add_layer(dependencies_dir, zip_function, resources)

        if not self._nested_stack_builder.is_any_function_added():
            LOG.debug("No function has been added for auto dependency layer creation")
            return template

        nested_template_location = str(self._get_template_folder().joinpath("adl_nested_template.yaml"))
        move_template(self._stack.location, nested_template_location, self._nested_stack_builder.build_as_dict())

        resources[NESTED_STACK_NAME] = self._nested_stack_builder.get_nested_stack_reference_resource(
            nested_template_location
        )
        return template

    def _get_template_folder(self) -> Path:
        return Path(self._stack.get_output_template_path(self._build_dir)).parent

    def _add_layer(self, dependencies_dir: str, function: Function, resources: Dict):
        layer_logical_id = NestedStackBuilder.get_layer_logical_id(function.full_path)
        layer_location = self.update_layer_folder(
            str(self._get_template_folder()), dependencies_dir, layer_logical_id, function.full_path, function.runtime
        )

        layer_output_key = self._nested_stack_builder.add_function(self._stack_name, layer_location, function)

        # add layer reference back to function
        function_properties = cast(Dict, resources.get(function.name)).get("Properties", {})
        function_layers = function_properties.get("Layers", [])
        function_layers.append({"Fn::GetAtt": [NESTED_STACK_NAME, f"Outputs.{layer_output_key}"]})
        function_properties["Layers"] = function_layers

    @staticmethod
    def _add_layer_readme_info(dependencies_dir: str, function_name: str):
        # add a simple README file for discoverability
        with open(os.path.join(dependencies_dir, "AWS_SAM_CLI_README"), "w+") as f:
            f.write(
                f"This layer contains dependencies of function {function_name} "
                "and automatically added by AWS SAM CLI command 'sam sync'"
            )

    @staticmethod
    def update_layer_folder(
        build_dir: str,
        dependencies_dir: str,
        layer_logical_id: str,
        function_logical_id: str,
        function_runtime: Optional[str],
    ) -> str:
        """
        Creates build folder for auto dependency layer by moving dependencies into sub folder which is defined
        by the runtime
        """
        if not function_runtime:
            raise InvalidRuntimeDefinitionForFunction(function_logical_id)

        layer_root_folder = Path(build_dir).joinpath(layer_logical_id)
        if layer_root_folder.exists():
            shutil.rmtree(layer_root_folder)
        layer_contents_folder = layer_root_folder.joinpath(get_layer_subfolder(function_runtime))
        layer_contents_folder.mkdir(BUILD_DIR_PERMISSIONS, parents=True)
        if os.path.isdir(dependencies_dir):
            osutils.copytree(dependencies_dir, str(layer_contents_folder))
        NestedStackManager._add_layer_readme_info(str(layer_root_folder), function_logical_id)
        return str(layer_root_folder)

    def _is_function_supported(self, function: Function):
        """
        Checks if function is built with current session and its runtime is supported
        """
        # check if function is built
        if function.full_path not in self._app_build_result.artifacts.keys():
            LOG.debug(
                "Function %s is not built within SAM CLI, skipping for auto dependency layer creation",
                function.full_path,
            )
            return False

        return self.is_runtime_supported(function.runtime)

    @staticmethod
    def is_runtime_supported(runtime: Optional[str]) -> bool:
        # check if runtime/language is supported
        if not runtime or not runtime.startswith(SUPPORTED_LANGUAGES):
            LOG.debug(
                "Runtime %s is not supported for auto dependency layer creation",
                runtime,
            )
            return False

        return True

    def _get_dependencies_dir(self, function_full_path: str) -> Optional[str]:
        """
        Returns dependency directory information for function
        """
        function_build_definition = self._app_build_result.build_graph.get_function_build_definition_with_full_path(
            function_full_path
        )

        return function_build_definition.dependencies_dir if function_build_definition else None
